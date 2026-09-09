from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.auth import AuthenticatedUser, require_user
from app.config import Settings
from app.cost_controls import COST_CONTROLS_SCHEMA_VERSION, CachedCostControlReader
from app.main import create_app
from app.quotas import InMemoryQuotaCounterStore, QuotaService
from app.synthetic_data import generate_synthetic_dataset

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


class ProfileRepositorySpy:
    def __init__(self) -> None:
        self.profiles = {}
        self.saves = 0
        self.reads = 0

    def save_profile(self, uid, profile) -> None:
        self.saves += 1
        self.profiles[uid] = profile

    def get_profile(self, uid):
        self.reads += 1
        return self.profiles.get(uid)


class JourneyRepositorySpy:
    def __init__(self) -> None:
        self.journeys = {}
        self.saves = 0

    def save_confirmed_journey(self, uid, journey) -> None:
        self.saves += 1
        self.journeys[uid] = journey

    def get_confirmed_journey(self, uid):
        return self.journeys.get(uid)


class RecommendationRepositorySpy:
    def __init__(self) -> None:
        self.dataset = generate_synthetic_dataset()
        self.reads = 0

    def get_dataset(self):
        self.reads += 1
        return self.dataset


class ConstantCostControlSource:
    def read(self):
        return {
            "schemaVersion": COST_CONTROLS_SCHEMA_VERSION,
            "geminiProjectDailyAllowance": 0,
            "maintenanceMode": False,
            "updatedAt": datetime(2026, 9, 3, 10, 30, tzinfo=UTC),
        }


class ProductionAnalyticsStub:
    environment = "production"

    def issue_profile_confirmed(self, **_kwargs):
        raise AssertionError("A synthetic production user must be rejected before analytics")


def configured_test_app(profile_repository, journey_repository, recommendation_repository):
    return create_app(
        Settings(
            app_env="test",
            adapter_mode="firebase_emulator",
            demo_mode=True,
            firebase_project_id="sakhicircle-sc715-emulator",
            firestore_database_id="(default)",
        ),
        profile_repository=profile_repository,
        journey_repository=journey_repository,
        recommendation_repository=recommendation_repository,
    )


def test_profile_journey_and_recommendation_flow_survives_new_api_instances() -> None:
    profiles = ProfileRepositorySpy()
    journeys = JourneyRepositorySpy()
    recommendations = RecommendationRepositorySpy()
    first_app = configured_test_app(profiles, journeys, recommendations)
    first_client = TestClient(first_app)

    saved = first_client.put("/api/v1/profile", headers=AUTH_HEADERS, json=PROFILE)
    assert saved.status_code == 200
    assert profiles.saves == 1

    second_app = configured_test_app(profiles, journeys, recommendations)
    second_client = TestClient(second_app)
    draft_response = second_client.post(
        "/api/v1/journeys",
        headers=AUTH_HEADERS,
        json={"startsOn": "2026-09-07"},
    )
    assert draft_response.status_code == 200
    assert journeys.saves == 0

    draft = draft_response.json()
    confirmed = second_client.put(
        f"/api/v1/journeys/{draft['journeyId']}",
        headers=AUTH_HEADERS,
        json=draft,
    )
    assert confirmed.status_code == 200
    assert journeys.saves == 1
    assert journeys.journeys["demo-meera"].status == "confirmed"

    third_app = configured_test_app(profiles, journeys, recommendations)
    third_client = TestClient(third_app)
    restored = third_client.get(
        "/api/v1/journeys/current",
        headers=AUTH_HEADERS,
    )
    assert restored.status_code == 200
    assert restored.json() == confirmed.json()

    match = third_client.get(
        "/api/v1/recommendations?type=partner",
        headers=AUTH_HEADERS,
    )
    assert match.status_code == 200
    assert match.json()["results"][0]["candidateId"] == "syn_partner_0001"
    assert recommendations.reads == 1
    assert not hasattr(third_app.state, "profile_store")
    assert not hasattr(third_app.state, "journey_store")
    assert not hasattr(third_app.state, "matching_dataset")


def test_current_journey_returns_404_when_the_user_has_no_confirmed_plan() -> None:
    app = configured_test_app(
        ProfileRepositorySpy(),
        JourneyRepositorySpy(),
        RecommendationRepositorySpy(),
    )

    response = TestClient(app).get(
        "/api/v1/journeys/current",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "confirmed_journey_not_found"


def test_repository_failure_returns_fixed_503_without_provider_or_learner_detail() -> None:
    class UnavailableProfiles(ProfileRepositorySpy):
        def get_profile(self, uid):
            from app.persistence import OperationalDataUnavailable

            raise OperationalDataUnavailable(f"provider failed while reading {uid}")

    app = configured_test_app(
        UnavailableProfiles(),
        JourneyRepositorySpy(),
        RecommendationRepositorySpy(),
    )
    response = TestClient(app).post(
        "/api/v1/journeys",
        headers=AUTH_HEADERS,
        json={"startsOn": "2026-09-07"},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "operational_data_unavailable"
    assert "provider" not in response.text
    assert "demo-meera" not in response.text


def test_production_has_no_process_memory_fallback_and_rejects_synthetic_identity() -> None:
    profiles = ProfileRepositorySpy()
    journeys = JourneyRepositorySpy()
    recommendations = RecommendationRepositorySpy()
    app = create_app(
        Settings(
            app_env="production",
            adapter_mode="production",
            firebase_project_id="patchamomma-2026-505415",
            firebase_app_id="web-app",
            firestore_database_id="(default)",
        ),
        profile_repository=profiles,
        journey_repository=journeys,
        recommendation_repository=recommendations,
        cost_control_reader=CachedCostControlReader(ConstantCostControlSource()),
        quota_service=QuotaService(InMemoryQuotaCounterStore()),
        analytics_service=ProductionAnalyticsStub(),
    )
    app.dependency_overrides[require_user] = lambda: AuthenticatedUser(
        uid="demo-meera",
        displayName="Synthetic learner",
        roles=["learner"],
        synthetic=True,
    )

    response = TestClient(app).put(
        "/api/v1/profile",
        headers={"Authorization": "Bearer overridden-test-token"},
        json=PROFILE,
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "production_identity_required"
    assert profiles.saves == 0
    assert not hasattr(app.state, "profile_store")
    assert not hasattr(app.state, "journey_store")
    assert not hasattr(app.state, "matching_dataset")
