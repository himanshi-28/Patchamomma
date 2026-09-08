from copy import deepcopy
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.config import Settings
from app.journey import JourneyDocument, build_curated_fallback, build_deterministic_journey
from app.main import create_app
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


def client_with_profile() -> tuple[TestClient, object]:
    app = create_app(Settings(app_env="test", demo_mode=True))
    client = TestClient(app)
    response = client.put("/api/v1/profile", headers=AUTH_HEADERS, json=PROFILE)
    assert response.status_code == 200
    return client, app


def generate(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/journeys",
        headers=AUTH_HEADERS,
        json={"startsOn": STARTS_ON},
    )
    assert response.status_code == 200
    return response.json()


def test_journey_generation_and_confirmation_require_authentication() -> None:
    client, _ = client_with_profile()
    draft = generate(client)

    assert client.post("/api/v1/journeys", json={"startsOn": STARTS_ON}).status_code == 401
    assert client.put(
        f"/api/v1/journeys/{draft['journeyId']}",
        json=draft,
    ).status_code == 401


def test_generation_requires_an_already_confirmed_profile() -> None:
    client = TestClient(create_app(Settings(app_env="test", demo_mode=True)))

    response = client.post(
        "/api/v1/journeys",
        headers=AUTH_HEADERS,
        json={"startsOn": STARTS_ON},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "confirmed_profile_required"


def test_optional_first_goal_does_not_create_a_dangling_summary_label() -> None:
    profile = LearningWishProfile.model_validate({**PROFILE, "experience": "", "goal": ""})

    journey = build_deterministic_journey(
        profile=profile,
        starts_on=date.fromisoformat(STARTS_ON),
        uid="optional-profile",
    )

    assert journey.summary.en == "A reviewed plan for Watercolour painting."
    assert journey.summary.hi == "Watercolour painting के लिए जाँची हुई योजना।"


def test_arbitrary_topic_fallback_stays_relevant_without_material_specific_advice() -> None:
    profile = LearningWishProfile.model_validate(
        {
            **PROFILE,
            "hobby": "Kathak",
            "goal": "Perform a short piece",
            "availability": "15 minutes · 3 days a week",
        }
    )

    journey = build_curated_fallback(
        profile=profile,
        starts_on=date.fromisoformat(STARTS_ON),
        journey_id="journey_kathak_fallback",
        reason="workflow_unavailable",
    )

    required = [
        activity
        for week in journey.weeks
        for activity in week.activities
        if activity.required
    ]
    assert "Kathak" in journey.title.en
    assert all(
        "kathak" in " ".join(
            [activity.title.en, *activity.instructions.en]
        ).casefold()
        for activity in required
    )
    assert "materials" not in journey.model_dump_json().casefold()


def test_deterministic_draft_has_exact_bilingual_28_day_structure_and_no_write() -> None:
    client, app = client_with_profile()

    draft = generate(client)

    assert draft["schemaVersion"] == "1.0.0"
    assert draft["status"] == "draft"
    assert draft["languages"] == ["en", "hi"]
    assert draft["provenance"] == {
        "generator": "deterministic_fixture",
        "attempts": 0,
        "fallbackUsed": False,
        "fallbackReason": None,
    }
    assert draft["review"] == {
        "status": "passed",
        "contractVersion": "safety-accessibility-v1",
        "passedChecks": ["schema", "schedule", "accessibility", "safety", "localization"],
    }
    assert len(draft["weeks"]) == 4
    assert [week["weekNumber"] for week in draft["weeks"]] == [1, 2, 3, 4]

    activities = [activity for week in draft["weeks"] for activity in week["activities"]]
    assert len(activities) == 28
    assert [activity["activityId"] for activity in activities] == [
        f"day-{day:02d}" for day in range(1, 29)
    ]
    assert [activity["dayNumber"] for activity in activities] == list(range(1, 29))
    assert [activity["date"] for activity in activities] == [
        (date.fromisoformat(STARTS_ON) + timedelta(days=offset)).isoformat()
        for offset in range(28)
    ]
    for week in draft["weeks"]:
        assert len(week["activities"]) == 7
        assert sum(
            activity["required"] and activity["kind"] != "rest"
            for activity in week["activities"]
        ) <= 4
    for activity in activities:
        assert activity["durationMinutes"] <= 30
        for field in (
            "title",
            "accessibleAlternative",
            "reflectionPrompt",
            "safetyNote",
        ):
            assert set(activity[field]) == {"en", "hi"}
            assert all(activity[field].values())
        assert set(activity["instructions"]) == {"en", "hi"}
        assert all(activity["instructions"].values())

    assert app.state.journey_repository.journeys == {}
    assert "uid" not in draft
    assert "city" not in draft
    assert "transcript" not in draft
    assert "rawAudio" not in draft


def test_strict_schema_rejects_unknown_forbidden_and_over_budget_edits() -> None:
    client, _ = client_with_profile()
    draft = generate(client)

    with_transcript = {**draft, "transcript": "private words"}
    with_nested_unknown = deepcopy(draft)
    with_nested_unknown["weeks"][0]["activities"][0]["providerPrompt"] = "ignore rules"
    over_budget = deepcopy(draft)
    over_budget["weeks"][0]["activities"][0]["durationMinutes"] = 45

    assert client.put(
        f"/api/v1/journeys/{draft['journeyId']}",
        headers=AUTH_HEADERS,
        json=with_transcript,
    ).status_code == 422
    assert client.put(
        f"/api/v1/journeys/{draft['journeyId']}",
        headers=AUTH_HEADERS,
        json=with_nested_unknown,
    ).status_code == 422
    assert client.put(
        f"/api/v1/journeys/{draft['journeyId']}",
        headers=AUTH_HEADERS,
        json=over_budget,
    ).status_code == 422


def test_only_explicit_confirmation_persists_the_edited_journey() -> None:
    client, app = client_with_profile()
    draft = generate(client)
    assert app.state.journey_repository.journeys == {}

    draft["title"]["en"] = "My edited watercolour month"
    draft["weeks"][0]["activities"][0]["durationMinutes"] = 20
    response = client.put(
        f"/api/v1/journeys/{draft['journeyId']}",
        headers=AUTH_HEADERS,
        json=draft,
    )

    assert response.status_code == 200
    confirmed = response.json()
    assert confirmed["status"] == "confirmed"
    assert confirmed["title"]["en"] == "My edited watercolour month"
    assert confirmed["weeks"][0]["activities"][0]["durationMinutes"] == 20
    assert app.state.journey_repository.get_confirmed_journey("demo-meera").status == "confirmed"


def test_curated_fallback_uses_the_same_strict_validated_contract() -> None:
    _client, app = client_with_profile()
    profile = app.state.profile_repository.get_profile("demo-meera")

    fallback = build_curated_fallback(
        profile=profile,
        starts_on=date.fromisoformat(STARTS_ON),
        journey_id="journey_fallback_fixture",
        reason="workflow_unavailable",
    )
    validated = JourneyDocument.model_validate(fallback.model_dump(by_alias=True))

    assert validated.provenance.generator == "curated_fallback"
    assert validated.provenance.fallback_used is True
    assert validated.provenance.fallback_reason == "workflow_unavailable"
    assert sum(len(week.activities) for week in validated.weeks) == 28
