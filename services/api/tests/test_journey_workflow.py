import asyncio
import json
from collections.abc import Callable
from datetime import date

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.journey import build_deterministic_journey
from app.journey_workflow import (
    GoogleAdkJourneyWorkflow,
    JourneyWorkflowInput,
    JourneyWorkflowResult,
    ReviewerOutput,
    WorkflowUnavailable,
    _parse_adk_output,
)
from app.main import create_app
from app.persistence import (
    InMemoryJourneyRepository,
    InMemoryProfileRepository,
    InMemoryRecommendationRepository,
)
from app.profile import LearningWishProfile

AUTH_HEADERS = {"Authorization": "Bearer demo-learner-token"}
PROFILE = {
    "hobby": "Watercolour painting",
    "experience": "Restarting after many years",
    "goal": "Paint a greeting card",
    "availability": "30 minutes · 4 days a week",
    "language": "Hindi",
    "accessibility": "Larger text · seated alternatives",
    "format": "At home · small online group",
    "planConsent": True,
    "matchingConsent": False,
    "city": "Pune",
}
STARTS_ON = "2026-08-26"


OutcomeFactory = Callable[[JourneyWorkflowInput], JourneyWorkflowResult]


class ScriptedWorkflow:
    def __init__(
        self,
        outcomes: list[OutcomeFactory | JourneyWorkflowResult | Exception],
        *,
        delay_seconds: float = 0,
    ) -> None:
        self.outcomes = outcomes
        self.delay_seconds = delay_seconds
        self.requests: list[JourneyWorkflowInput] = []

    async def run(self, request: JourneyWorkflowInput) -> JourneyWorkflowResult:
        self.requests.append(request)
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        outcome = self.outcomes[len(self.requests) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome(request) if callable(outcome) else outcome


def valid_result(request: JourneyWorkflowInput) -> JourneyWorkflowResult:
    profile = LearningWishProfile.model_validate(PROFILE)
    payload = build_deterministic_journey(
        profile=profile,
        starts_on=request.starts_on,
        uid="workflow-fixture",
    ).model_dump(by_alias=True, mode="json")
    payload["journeyId"] = request.journey_id
    payload["provenance"] = {
        "generator": "gemini_adk",
        "attempts": request.attempt,
        "fallbackUsed": False,
        "fallbackReason": None,
    }
    return JourneyWorkflowResult(review_code="pass", document=payload)


def invalid_result(_request: JourneyWorkflowInput) -> JourneyWorkflowResult:
    return JourneyWorkflowResult(
        review_code="pass",
        document={"schemaVersion": "1.0.0", "unexpected": "discard me"},
    )


def client_with_profile(
    workflow: ScriptedWorkflow | None,
    *,
    journey_adapter_mode: str = "gemini_adk",
    attempt_timeout_seconds: float = 10,
) -> tuple[TestClient, object]:
    app = create_app(
        Settings(
            app_env="test",
            demo_mode=True,
            journey_adapter_mode=journey_adapter_mode,
            journey_attempt_timeout_seconds=attempt_timeout_seconds,
        ),
        journey_workflow=workflow,
    )
    client = TestClient(app)
    response = client.put("/api/v1/profile", headers=AUTH_HEADERS, json=PROFILE)
    assert response.status_code == 200
    return client, app


def generate(client: TestClient):
    return client.post(
        "/api/v1/journeys",
        headers=AUTH_HEADERS,
        json={"startsOn": STARTS_ON},
    )


def test_gemini_workflow_first_pass_returns_strict_bilingual_allowlisted_draft() -> None:
    workflow = ScriptedWorkflow([valid_result])
    client, app = client_with_profile(workflow)

    response = generate(client)

    assert response.status_code == 200
    draft = response.json()
    assert draft["provenance"] == {
        "generator": "gemini_adk",
        "attempts": 1,
        "fallbackUsed": False,
        "fallbackReason": None,
    }
    assert draft["languages"] == ["en", "hi"]
    activities = [activity for week in draft["weeks"] for activity in week["activities"]]
    assert len(activities) == 28
    assert all(activity["accessibleAlternative"]["en"] for activity in activities)
    assert all(activity["accessibleAlternative"]["hi"] for activity in activities)
    assert all(activity["safetyNote"]["en"] for activity in activities)
    assert all(activity["safetyNote"]["hi"] for activity in activities)
    assert app.state.journey_repository.journeys == {}
    assert app.state.integration_call_counts == {"ai": 1, "paid": 0}

    sent = workflow.requests[0].model_dump(by_alias=True, mode="json")
    assert set(sent) == {
        "hobby",
        "experience",
        "goal",
        "availability",
        "planWeeks",
        "language",
        "accessibility",
        "format",
        "startsOn",
        "journeyId",
        "attempt",
        "rejectionCodes",
    }
    assert sent["planWeeks"] == 4
    assert sent["rejectionCodes"] == []
    assert {
        "city",
        "planConsent",
        "matchingConsent",
        "transcript",
        "rawAudio",
        "uid",
    }.isdisjoint(sent)


def test_invalid_output_retries_the_complete_workflow_once_then_returns_valid_output() -> None:
    workflow = ScriptedWorkflow([invalid_result, valid_result])
    client, app = client_with_profile(workflow)

    response = generate(client)

    assert response.status_code == 200
    assert response.json()["provenance"]["generator"] == "gemini_adk"
    assert response.json()["provenance"]["attempts"] == 2
    assert len(workflow.requests) == 2
    assert workflow.requests[1].rejection_codes == ["validation"]
    assert app.state.integration_call_counts == {"ai": 2, "paid": 0}


def test_reviewer_rejection_twice_returns_complete_reviewed_fallback() -> None:
    rejected = JourneyWorkflowResult(review_code="safety", document=None)
    workflow = ScriptedWorkflow([rejected, rejected])
    client, app = client_with_profile(workflow)

    response = generate(client)

    assert response.status_code == 200
    assert response.json()["provenance"] == {
        "generator": "curated_fallback",
        "attempts": 2,
        "fallbackUsed": True,
        "fallbackReason": "review_failed_twice",
    }
    assert workflow.requests[1].rejection_codes == ["safety"]
    assert app.state.journey_repository.journeys == {}


def test_localization_rejection_twice_uses_specific_fallback_reason() -> None:
    rejected = JourneyWorkflowResult(review_code="localization", document=None)
    workflow = ScriptedWorkflow([rejected, rejected])
    client, _ = client_with_profile(workflow)

    response = generate(client)

    assert response.status_code == 200
    assert response.json()["provenance"]["fallbackReason"] == "localization_failed_twice"


def test_unavailable_provider_skips_retry_and_returns_fallback_without_provider_detail() -> None:
    workflow = ScriptedWorkflow([WorkflowUnavailable("secret provider detail")])
    client, app = client_with_profile(workflow)

    response = generate(client)

    assert response.status_code == 200
    assert response.json()["provenance"] == {
        "generator": "curated_fallback",
        "attempts": 1,
        "fallbackUsed": True,
        "fallbackReason": "workflow_unavailable",
    }
    assert "secret provider detail" not in response.text
    assert len(workflow.requests) == 1
    assert app.state.integration_call_counts == {"ai": 1, "paid": 0}


def test_attempt_timeout_returns_fallback_without_a_second_workflow_call() -> None:
    workflow = ScriptedWorkflow([valid_result], delay_seconds=0.02)
    client, _ = client_with_profile(workflow, attempt_timeout_seconds=0.001)

    response = generate(client)

    assert response.status_code == 200
    assert response.json()["provenance"]["fallbackReason"] == "workflow_timeout"
    assert response.json()["provenance"]["attempts"] == 1
    assert len(workflow.requests) == 1


def test_deterministic_mode_never_invokes_an_injected_workflow_or_paid_api() -> None:
    workflow = ScriptedWorkflow([valid_result])
    client, app = client_with_profile(workflow, journey_adapter_mode="deterministic")

    response = generate(client)

    assert response.status_code == 200
    assert response.json()["provenance"]["generator"] == "deterministic_fixture"
    assert workflow.requests == []
    assert app.state.integration_call_counts == {"ai": 0, "paid": 0}


def test_missing_gemini_configuration_fails_closed_instead_of_using_fallback() -> None:
    client, app = client_with_profile(None)

    response = generate(client)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "journey_configuration_required"
    assert "key" not in response.text.lower()
    assert app.state.integration_call_counts == {"ai": 0, "paid": 0}
    assert app.state.journey_repository.journeys == {}


def test_server_rejects_workflow_output_that_changes_trusted_identity_or_start_date() -> None:
    def changed_identity(request: JourneyWorkflowInput) -> JourneyWorkflowResult:
        result = valid_result(request)
        assert result.document is not None
        result.document["journeyId"] = "journey_model_chosen_identifier"
        result.document["startsOn"] = date(2026, 9, 1).isoformat()
        return result

    workflow = ScriptedWorkflow([changed_identity, changed_identity])
    client, _ = client_with_profile(workflow)

    response = generate(client)

    assert response.status_code == 200
    assert response.json()["provenance"]["generator"] == "curated_fallback"
    assert response.json()["provenance"]["fallbackReason"] == "validation_failed_twice"
    assert response.json()["startsOn"] == STARTS_ON


def test_real_adk_pipeline_is_fixed_to_three_structured_stages_without_tools() -> None:
    from google import genai

    client = genai.Client(api_key="test-key-is-never-used")
    try:
        pipeline = GoogleAdkJourneyWorkflow.build_pipeline(
            client=client,
            model_name="gemini-3.7-flash",
        )
    finally:
        client.close()

    assert pipeline.name == "sakhicircle_bounded_journey_workflow"
    assert [agent.name for agent in pipeline.sub_agents] == [
        "journey_plan_generator",
        "journey_safety_accessibility_reviewer",
        "journey_english_hindi_localizer",
    ]
    assert [agent.output_key for agent in pipeline.sub_agents] == [
        "english_plan",
        "review_result",
        "localized_journey",
    ]
    assert all(agent.tools == [] for agent in pipeline.sub_agents)
    assert all(agent.output_schema is not None for agent in pipeline.sub_agents)
    assert all(
        agent.generate_content_config.temperature is None
        for agent in pipeline.sub_agents
    )
    assert all(
        "additionalProperties" not in json.dumps(agent.output_schema.model_json_schema())
        for agent in pipeline.sub_agents
    )
    assert all(
        constraint not in json.dumps(agent.output_schema.model_json_schema())
        for agent in pipeline.sub_agents
        for constraint in ("minItems", "maxItems", "minLength", "maxLength")
    )
    run_config = GoogleAdkJourneyWorkflow.build_run_config()
    assert run_config.max_llm_calls == 3
    assert run_config.telemetry.content_capturing_mode_value == ""


def test_adk_validated_dictionary_state_is_accepted_without_json_reparsing() -> None:
    review = _parse_adk_output(ReviewerOutput, {"reviewCode": "pass"})

    assert review.review_code == "pass"


def test_gemini_prompts_require_topic_specific_plans_and_reject_generic_output() -> None:
    from app.journey_workflow import PLAN_INSTRUCTION, REVIEW_INSTRUCTION

    assert "specific to the confirmed hobby" in PLAN_INSTRUCTION
    assert "could apply unchanged to a different hobby" in REVIEW_INSTRUCTION


def test_production_gemini_configuration_requires_explicit_paid_calls_and_credentials() -> None:
    base = {
        "app_env": "production",
        "adapter_mode": "production",
        "firebase_project_id": "sakhicircle-production",
        "firebase_app_id": "web-app",
        "journey_adapter_mode": "gemini_adk",
    }
    with pytest.raises(ValidationError, match="PAID_API_CALLS_ENABLED"):
        Settings(**base)
    with pytest.raises(ValidationError, match="SAKHI_GEMINI_API_KEY"):
        Settings(**base, paid_api_calls_enabled=True)

    vertex = Settings(
        **base,
        paid_api_calls_enabled=True,
        gemini_backend="vertex_ai",
        gemini_location="global",
    )
    assert vertex.gemini_api_key is None
    assert vertex.gemini_backend == "vertex_ai"
    assert vertex.journey_attempt_timeout_seconds == 30
    assert vertex.profile_extraction_timeout_seconds == 10


def test_production_uses_separate_models_for_extraction_and_adk_planning() -> None:
    settings = Settings(
        app_env="production",
        adapter_mode="production",
        firebase_project_id="sakhicircle-production",
        firebase_app_id="web-app",
        journey_adapter_mode="gemini_adk",
        paid_api_calls_enabled=True,
        gemini_backend="vertex_ai",
        gemini_model="gemini-3.7-flash",
        journey_gemini_model="gemini-2.5-flash",
    )

    app = create_app(
        settings,
        cost_control_reader=object(),
        quota_service=object(),
        analytics_service=object(),
        profile_repository=InMemoryProfileRepository(),
        journey_repository=InMemoryJourneyRepository(),
        recommendation_repository=InMemoryRecommendationRepository(),
    )

    assert app.state.profile_extractor._model == "gemini-3.7-flash"
    assert app.state.profile_extractor._timeout_seconds == 10
    assert app.state.journey_workflow._model == "gemini-2.5-flash"
