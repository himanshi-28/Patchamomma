from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.analytics import (
    AnalyticsKeyring,
    AnalyticsService,
    InMemoryAnalyticsBackend,
    StaticTaskTokenVerifier,
    TaskAuthClaims,
)
from app.auth import AuthenticatedUser, require_user
from app.config import Settings
from app.cost_controls import CostControlState
from app.main import create_app

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
    "matchingConsent": True,
    "city": "Pune",
}
NOW = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)
TASK_AUDIENCE = "https://api.example.test/internal/v1/analytics/deliver"
TASK_IDENTITY = "sakhi-task-delivery@test-project.iam.gserviceaccount.com"
VALID_TASK_CLAIMS = TaskAuthClaims(
    issuer="https://accounts.google.com",
    audience=TASK_AUDIENCE,
    service_account=TASK_IDENTITY,
)


class AvailableCostControlReader:
    def read(self) -> CostControlState:
        return CostControlState(
            schemaVersion="cost-controls-v1.0.0",
            geminiProjectDailyAllowance=0,
            maintenanceMode=False,
            updatedAt=NOW,
        )


def make_analytics() -> tuple[AnalyticsService, InMemoryAnalyticsBackend]:
    backend = InMemoryAnalyticsBackend()
    event_ids = iter(
        (
            "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d1",
            "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d2",
            "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d3",
            "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d4",
        )
    )
    service = AnalyticsService(
        project_id="test-project",
        environment="test",
        keyring=AnalyticsKeyring(
            project_id="test-project",
            keys={"8": b"current-test-key"},
            current_version="8",
        ),
        backend=backend,
        clock=lambda: NOW,
        event_id_factory=lambda _now: next(event_ids),
        nonce_factory=lambda: "fixed-test-nonce",
        task_audience=TASK_AUDIENCE,
        task_service_account=TASK_IDENTITY,
    )
    return service, backend


def make_client() -> tuple[TestClient, object, AnalyticsService, InMemoryAnalyticsBackend]:
    analytics, backend = make_analytics()
    app = create_app(
        Settings(app_env="test", demo_mode=True),
        analytics_service=analytics,
        task_token_verifier=StaticTaskTokenVerifier(
            {"valid-task-token": VALID_TASK_CLAIMS}
        ),
    )
    return TestClient(app), app, analytics, backend


def save_profile(client: TestClient):
    response = client.put("/api/v1/profile", headers=AUTH_HEADERS, json=PROFILE)
    assert response.status_code == 200
    return response


def create_journey(client: TestClient):
    response = client.post(
        "/api/v1/journeys",
        headers=AUTH_HEADERS,
        json={"startsOn": "2026-09-03"},
    )
    assert response.status_code == 200
    return response


def test_successful_business_routes_emit_all_four_server_owned_receipts() -> None:
    client, _app, _analytics, backend = make_client()

    profile = save_profile(client)
    draft = create_journey(client)
    confirmed = client.put(
        f"/api/v1/journeys/{draft.json()['journeyId']}",
        headers=AUTH_HEADERS,
        json=draft.json(),
    )
    recommendation = client.get(
        "/api/v1/recommendations?type=partner",
        headers=AUTH_HEADERS,
    )

    responses = (profile, draft, confirmed, recommendation)
    assert [response.status_code for response in responses] == [200, 200, 200, 200]
    assert [record.event_name for record in backend.outbox.values()] == [
        "profile_confirmed",
        "journey_draft_created",
        "journey_confirmed",
        "recommendation_presented",
    ]
    for response in responses:
        assert response.headers["X-Sakhi-Analytics-Event-Id"]
        assert response.headers["X-Sakhi-Analytics-Receipt"].startswith("v1.")
    assert set(profile.json()) == {"status", "profile"}
    assert "analytics" not in recommendation.json()


def test_cors_exposes_only_the_two_analytics_receipt_headers() -> None:
    client, _app, _analytics, _backend = make_client()

    response = client.put(
        "/api/v1/profile",
        headers={**AUTH_HEADERS, "Origin": "http://localhost:5173"},
        json=PROFILE,
    )

    exposed = {
        item.strip()
        for item in response.headers["Access-Control-Expose-Headers"].split(",")
    }
    assert exposed == {
        "X-Sakhi-Analytics-Event-Id",
        "X-Sakhi-Analytics-Receipt",
    }


def test_failed_or_unconfirmed_actions_create_no_receipt_outbox_or_task() -> None:
    client, _app, _analytics, backend = make_client()

    failed = client.post(
        "/api/v1/journeys",
        headers=AUTH_HEADERS,
        json={"startsOn": "2026-09-03"},
    )
    invalid = client.put(
        "/api/v1/profile",
        headers=AUTH_HEADERS,
        json={**PROFILE, "planConsent": False},
    )

    assert failed.status_code == 409
    assert invalid.status_code == 422
    assert "X-Sakhi-Analytics-Receipt" not in failed.headers
    assert backend.outbox == {}
    assert backend.tasks == {}


def test_enqueue_failure_never_rolls_back_product_success_and_receipt_can_resume() -> None:
    client, _app, _analytics, backend = make_client()
    backend.fail_next_enqueues = 1

    response = save_profile(client)

    assert response.status_code == 200
    assert response.headers["X-Sakhi-Analytics-Receipt"].startswith("v1.")
    assert len(backend.outbox) == 1
    assert backend.tasks == {}

    resumed = client.post(
        "/api/v1/analytics/events",
        headers=AUTH_HEADERS,
        json={
            "schemaVersion": "analytics-v1.0.0",
            "eventId": response.headers["X-Sakhi-Analytics-Event-Id"],
            "actionReceipt": response.headers["X-Sakhi-Analytics-Receipt"],
        },
    )
    assert resumed.status_code == 202
    assert resumed.json()["status"] == "queued"
    assert len(backend.tasks) == 1


FORBIDDEN_CLIENT_FIELDS = (
    "eventName",
    "properties",
    "outcome",
    "uid",
    "subjectKey",
    "pseudonym",
    "environment",
    "eventTimestamp",
    "eventDate",
    "ipAddress",
    "userAgent",
    "deviceId",
    "traceId",
    "dashboardDimensions",
    "transcript",
    "rawText",
    "rawAudio",
    "city",
    "candidateId",
)


@pytest.mark.parametrize("forbidden_field", FORBIDDEN_CLIENT_FIELDS)
def test_receipt_endpoint_rejects_every_client_chosen_or_content_field(
    forbidden_field: str,
) -> None:
    client, _app, _analytics, backend = make_client()
    issued = save_profile(client)
    request = {
        "schemaVersion": "analytics-v1.0.0",
        "eventId": issued.headers["X-Sakhi-Analytics-Event-Id"],
        "actionReceipt": issued.headers["X-Sakhi-Analytics-Receipt"],
        forbidden_field: "forged-value",
    }
    before = dict(backend.outbox)

    response = client.post(
        "/api/v1/analytics/events",
        headers=AUTH_HEADERS,
        json=request,
    )

    assert response.status_code == 422
    assert backend.outbox == before


def test_unsigned_or_forged_outcome_produces_no_occurrence() -> None:
    client, _app, _analytics, backend = make_client()

    response = client.post(
        "/api/v1/analytics/events",
        headers=AUTH_HEADERS,
        json={
            "schemaVersion": "analytics-v1.0.0",
            "eventId": "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d1",
            "actionReceipt": "unsigned",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_analytics_receipt"
    assert backend.outbox == {}


def test_request_larger_than_two_kib_is_rejected_before_outbox_change() -> None:
    client, _app, _analytics, backend = make_client()

    response = client.post(
        "/api/v1/analytics/events",
        headers=AUTH_HEADERS,
        json={
            "schemaVersion": "analytics-v1.0.0",
            "eventId": "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d1",
            "actionReceipt": "x" * 2049,
        },
    )

    assert response.status_code == 422
    assert backend.outbox == {}


def test_two_identical_signed_requests_return_one_bigquery_row() -> None:
    client, _app, analytics, backend = make_client()
    issued = save_profile(client)
    payload = {
        "schemaVersion": "analytics-v1.0.0",
        "eventId": issued.headers["X-Sakhi-Analytics-Event-Id"],
        "actionReceipt": issued.headers["X-Sakhi-Analytics-Receipt"],
    }

    queued = client.post("/api/v1/analytics/events", headers=AUTH_HEADERS, json=payload)
    task = next(iter(backend.tasks.values()))
    analytics.deliver(task.delivery_handle, claims=VALID_TASK_CLAIMS)
    duplicate = client.post("/api/v1/analytics/events", headers=AUTH_HEADERS, json=payload)

    assert queued.status_code == 202
    assert duplicate.status_code == 200
    assert duplicate.json() == {
        "schemaVersion": "analytics-v1.0.0",
        "eventId": payload["eventId"],
        "status": "written",
        "duplicate": True,
    }
    assert len(backend.warehouse_rows) == 1


def test_receipt_event_mismatch_is_409_and_preserves_first_occurrence() -> None:
    client, _app, _analytics, backend = make_client()
    issued = save_profile(client)
    original = dict(backend.outbox)

    response = client.post(
        "/api/v1/analytics/events",
        headers=AUTH_HEADERS,
        json={
            "schemaVersion": "analytics-v1.0.0",
            "eventId": "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d2",
            "actionReceipt": issued.headers["X-Sakhi-Analytics-Receipt"],
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "event_id_conflict"
    assert backend.outbox == original


@pytest.mark.parametrize(
    "headers",
    (
        {},
        {"Authorization": "Bearer firebase-browser-token"},
        {"Authorization": "Bearer wrong-task-token"},
    ),
)
def test_internal_task_route_rejects_missing_browser_and_wrong_oidc_tokens(
    headers: dict[str, str],
) -> None:
    client, _app, _analytics, backend = make_client()
    save_profile(client)
    task = next(iter(backend.tasks.values()))

    response = client.post(
        "/internal/v1/analytics/deliver",
        headers=headers,
        json={"deliveryHandle": task.delivery_handle},
    )

    assert response.status_code == 403
    assert backend.warehouse_rows == {}
    assert next(iter(backend.outbox.values())).attempt_count == 0


def test_internal_task_route_accepts_only_verified_issuer_audience_and_identity() -> None:
    client, app, _analytics, backend = make_client()
    save_profile(client)
    task = next(iter(backend.tasks.values()))
    body = {"deliveryHandle": task.delivery_handle}

    for changed_claim in (
        VALID_TASK_CLAIMS.model_copy(update={"issuer": "https://attacker.example"}),
        VALID_TASK_CLAIMS.model_copy(update={"audience": "https://wrong.example"}),
        VALID_TASK_CLAIMS.model_copy(update={"service_account": "wrong@test-project.iam.gserviceaccount.com"}),
    ):
        app.state.task_token_verifier = StaticTaskTokenVerifier(
            {"valid-task-token": changed_claim}
        )
        denied = client.post(
            "/internal/v1/analytics/deliver",
            headers={"Authorization": "Bearer valid-task-token"},
            json=body,
        )
        assert denied.status_code == 403

    app.state.task_token_verifier = StaticTaskTokenVerifier(
        {"valid-task-token": VALID_TASK_CLAIMS}
    )
    accepted = client.post(
        "/internal/v1/analytics/deliver",
        headers={"Authorization": "Bearer valid-task-token"},
        json=body,
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "written"


def test_demo_identity_is_rejected_by_production_analytics_adapter() -> None:
    analytics, backend = make_analytics()
    analytics.environment = "production"
    app = create_app(
        Settings(app_env="test", demo_mode=True),
        analytics_service=analytics,
        task_token_verifier=StaticTaskTokenVerifier(
            {"valid-task-token": VALID_TASK_CLAIMS}
        ),
    )
    client = TestClient(app)

    response = client.put("/api/v1/profile", headers=AUTH_HEADERS, json=PROFILE)

    assert response.status_code == 200
    assert "X-Sakhi-Analytics-Receipt" not in response.headers
    assert backend.outbox == {}

    analytics_attempt = client.post(
        "/api/v1/analytics/events",
        headers=AUTH_HEADERS,
        json={
            "schemaVersion": "analytics-v1.0.0",
            "eventId": "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d1",
            "actionReceipt": "unsigned",
        },
    )
    assert analytics_attempt.status_code == 403
    assert analytics_attempt.json()["detail"]["code"] == "analytics_production_only"


def test_production_analytics_configuration_fails_closed_without_network_fallback() -> None:
    settings = Settings(
        app_env="production",
        adapter_mode="production",
        firebase_project_id="test-project",
        firebase_app_id="web-app",
        firestore_database_id="(default)",
    )
    with patch("app.analytics_google.build_production_analytics") as factory:
        factory.side_effect = RuntimeError("missing analytics configuration")
        app = create_app(
            settings,
            cost_control_reader=AvailableCostControlReader(),
        )

    app.dependency_overrides[require_user] = lambda: AuthenticatedUser(
        uid="firebase-user",
        displayName="SakhiCircle member",
        roles=["learner"],
        synthetic=False,
    )
    client = TestClient(app)
    response = client.post(
        "/api/v1/analytics/events",
        headers={"Authorization": "Bearer valid", "X-Firebase-AppCheck": "valid"},
        json={
            "schemaVersion": "analytics-v1.0.0",
            "eventId": "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d1",
            "actionReceipt": "v1.payload.signature",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "analytics_configuration_required"
    factory.assert_called_once()
