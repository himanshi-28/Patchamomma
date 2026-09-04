from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.auth import AuthenticatedUser, require_user
from app.config import Settings
from app.cost_controls import (
    COST_CONTROLS_SCHEMA_VERSION,
    GEMINI_DEPLOYMENT_DAILY_MAXIMUM,
    CachedCostControlReader,
    CostControlState,
    CostControlStateUnavailable,
)
from app.main import create_app
from app.persistence import (
    InMemoryJourneyRepository,
    InMemoryProfileRepository,
    InMemoryRecommendationRepository,
)
from app.quotas import InMemoryQuotaCounterStore, QuotaService

AUTH_HEADERS = {"Authorization": "Bearer test-token"}
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


class MutableClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class MutableCostControlSource:
    def __init__(self, value: object) -> None:
        self.value = value
        self.read_count = 0

    def read(self) -> object:
        self.read_count += 1
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class CountingWorkflow:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, _request: object) -> object:
        self.calls += 1
        raise AssertionError("A denied workflow must make zero model calls")


def controls(*, allowance: int = 20, maintenance: bool = False) -> dict[str, object]:
    return {
        "schemaVersion": COST_CONTROLS_SCHEMA_VERSION,
        "geminiProjectDailyAllowance": allowance,
        "maintenanceMode": maintenance,
        "updatedAt": datetime(2026, 9, 2, 8, 0, tzinfo=UTC),
    }


def production_client(
    source: MutableCostControlSource,
    workflow: CountingWorkflow,
    *,
    now: datetime = datetime(2026, 9, 2, 8, 30, tzinfo=UTC),
) -> tuple[TestClient, object]:
    clock = MutableClock(now)
    app = create_app(
        Settings(
            app_env="production",
            adapter_mode="production",
            journey_adapter_mode="gemini_adk",
            paid_api_calls_enabled=True,
            gemini_api_key="test-key-is-never-used",
            firebase_project_id="patchamomma-2026-505415",
            firebase_app_id="test-web-app",
            firestore_database_id="(default)",
        ),
        journey_workflow=workflow,
        cost_control_reader=CachedCostControlReader(source, clock=clock),
        quota_service=QuotaService(InMemoryQuotaCounterStore(), clock=clock),
        profile_repository=InMemoryProfileRepository(),
        journey_repository=InMemoryJourneyRepository(),
        recommendation_repository=InMemoryRecommendationRepository(),
    )
    app.dependency_overrides[require_user] = lambda: AuthenticatedUser(
        uid="member-1",
        displayName="Member",
        roles=["learner"],
    )
    client = TestClient(app)
    saved = client.put("/api/v1/profile", headers=AUTH_HEADERS, json=PROFILE)
    assert saved.status_code == 200
    return client, app


def test_cost_control_state_is_strict_and_cannot_raise_the_deployment_maximum() -> None:
    assert GEMINI_DEPLOYMENT_DAILY_MAXIMUM == 20
    assert CostControlState.model_validate(controls()).gemini_project_daily_allowance == 20

    with pytest.raises(ValidationError):
        CostControlState.model_validate(controls(allowance=21))
    with pytest.raises(ValidationError):
        CostControlState.model_validate({**controls(), "schemaVersion": "future-version"})
    with pytest.raises(ValidationError):
        CostControlState.model_validate({**controls(), "unexpected": True})


def test_runtime_reader_is_read_only_and_refreshes_before_cache_exceeds_60_seconds() -> None:
    clock = MutableClock(datetime(2026, 9, 2, 8, 0, tzinfo=UTC))
    source = MutableCostControlSource(controls(allowance=20))
    reader = CachedCostControlReader(source, clock=clock)

    assert not hasattr(reader, "write")
    assert reader.read().gemini_project_daily_allowance == 20
    source.value = controls(allowance=0)
    clock.now += timedelta(seconds=60)
    assert reader.read().gemini_project_daily_allowance == 20
    clock.now += timedelta(microseconds=1)
    assert reader.read().gemini_project_daily_allowance == 0
    assert source.read_count == 2


@pytest.mark.parametrize(
    "bad_value",
    [None, {"schemaVersion": COST_CONTROLS_SCHEMA_VERSION}, RuntimeError("unreadable")],
)
def test_missing_invalid_or_unreadable_control_state_fails_closed(bad_value: object) -> None:
    reader = CachedCostControlReader(MutableCostControlSource(bad_value))

    with pytest.raises(CostControlStateUnavailable):
        reader.read()


def test_zero_gemini_allowance_returns_429_before_any_workflow_call() -> None:
    workflow = CountingWorkflow()
    client, app = production_client(MutableCostControlSource(controls(allowance=0)), workflow)

    response = client.post(
        "/api/v1/journeys",
        headers=AUTH_HEADERS,
        json={"startsOn": "2026-09-03"},
    )

    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "gemini_quota_exceeded"
    assert int(response.headers["Retry-After"]) > 0
    assert workflow.calls == 0
    assert app.state.integration_call_counts == {"ai": 0, "paid": 0}


def test_missing_control_document_denies_paid_work_but_keeps_non_paid_routes_available() -> None:
    workflow = CountingWorkflow()
    client, app = production_client(MutableCostControlSource(None), workflow)

    session = client.get("/api/v1/auth/session", headers=AUTH_HEADERS)
    journey = client.post(
        "/api/v1/journeys",
        headers=AUTH_HEADERS,
        json={"startsOn": "2026-09-03"},
    )

    assert session.status_code == 200
    assert journey.status_code == 503
    assert journey.json()["detail"]["code"] == "cost_controls_unavailable"
    assert workflow.calls == 0
    assert app.state.integration_call_counts == {"ai": 0, "paid": 0}


def test_maintenance_preserves_health_and_stops_api_work_before_auth_or_paid_calls() -> None:
    workflow = CountingWorkflow()
    source = MutableCostControlSource(controls(maintenance=True))
    preview_origin = (
        "https://patchamomma-2026-505415--sc720-preview-z1y9xrdl.web.app"
    )
    app = create_app(
        Settings(
            app_env="production",
            adapter_mode="production",
            journey_adapter_mode="gemini_adk",
            paid_api_calls_enabled=True,
            gemini_api_key="test-key-is-never-used",
            firebase_project_id="patchamomma-2026-505415",
            firebase_app_id="test-web-app",
            firestore_database_id="(default)",
            allowed_origins=[preview_origin],
        ),
        journey_workflow=workflow,
        cost_control_reader=CachedCostControlReader(source),
        quota_service=QuotaService(InMemoryQuotaCounterStore()),
    )
    client = TestClient(app)

    health = client.get("/health")
    ready = client.get("/ready")
    preflight = client.options(
        "/api/v1/profile",
        headers={
            "Origin": preview_origin,
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "authorization,x-firebase-appcheck",
        },
    )
    protected = client.put(
        "/api/v1/profile",
        headers={"Origin": preview_origin},
        json=PROFILE,
    )

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert ready.status_code == 503
    assert ready.json()["status"] == "maintenance"
    assert preflight.status_code == 200
    assert preflight.headers["Access-Control-Allow-Origin"] == preview_origin
    assert preflight.headers["Access-Control-Allow-Credentials"] == "true"
    assert protected.status_code == 503
    assert protected.json()["detail"]["code"] == "maintenance_mode"
    assert protected.headers["Retry-After"] == "60"
    assert protected.headers["Access-Control-Allow-Origin"] == preview_origin
    assert protected.headers["Access-Control-Allow-Credentials"] == "true"
    assert workflow.calls == 0
    assert app.state.integration_call_counts == {"ai": 0, "paid": 0}


def test_local_deterministic_mode_ignores_production_control_state() -> None:
    source = MutableCostControlSource(RuntimeError("must not be read locally"))
    app = create_app(
        Settings(app_env="test", demo_mode=True, journey_adapter_mode="deterministic"),
        cost_control_reader=CachedCostControlReader(source),
    )
    client = TestClient(app)

    saved = client.put(
        "/api/v1/profile",
        headers={"Authorization": "Bearer demo-learner-token"},
        json=PROFILE,
    )
    journey = client.post(
        "/api/v1/journeys",
        headers={"Authorization": "Bearer demo-learner-token"},
        json={"startsOn": "2026-09-03"},
    )

    assert saved.status_code == 200
    assert journey.status_code == 200
    assert source.read_count == 0
