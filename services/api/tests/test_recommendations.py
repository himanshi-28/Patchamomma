from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth import AuthenticatedUser
from app.config import Settings
from app.main import create_app
from app.persistence import (
    InMemoryJourneyRepository,
    InMemoryProfileRepository,
    OperationalDataUnavailable,
)
from app.profile import LearningWishProfile
from app.quotas import InMemoryQuotaCounterStore, QuotaService

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


def client_with_profile(profile: dict | None = None):
    app = create_app(Settings(app_env="test", demo_mode=True))
    client = TestClient(app)
    response = client.put(
        "/api/v1/profile",
        headers=AUTH_HEADERS,
        json=profile or PROFILE,
    )
    assert response.status_code == 200
    return client, app


def test_recommendations_require_authentication_confirmed_profile_and_active_consent() -> None:
    app = create_app(Settings(app_env="test", demo_mode=True))
    client = TestClient(app)

    assert client.get("/api/v1/recommendations?type=partner").status_code == 401
    without_profile = client.get(
        "/api/v1/recommendations?type=partner",
        headers=AUTH_HEADERS,
    )
    assert without_profile.status_code == 409
    assert without_profile.json()["detail"]["code"] == "profile_confirmation_required"

    saved = client.put(
        "/api/v1/profile",
        headers=AUTH_HEADERS,
        json={**PROFILE, "matchingConsent": False},
    )
    assert saved.status_code == 200
    without_consent = client.get(
        "/api/v1/recommendations?type=partner",
        headers=AUTH_HEADERS,
    )
    assert without_consent.status_code == 409
    assert without_consent.json()["detail"]["code"] == "matching_consent_required"


def test_explicit_get_returns_one_minimal_explainable_synthetic_partner_without_writing() -> None:
    client, app = client_with_profile()
    stores_before = {
        "profile": dict(app.state.profile_repository.profiles),
        "journey": dict(app.state.journey_repository.journeys),
    }

    response = client.get(
        "/api/v1/recommendations?type=partner",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["contractVersion"] == "matching-v1.0.0"
    assert payload["recommendationType"] == "partner"
    assert payload["source"] == "deterministic_synthetic"
    assert payload["synthetic"] is True
    assert payload["status"] == "matched"
    assert payload["scoreThreshold"] == 65
    assert payload["resultLimit"] == 3
    assert len(payload["results"]) == 1
    assert len(payload["demoProfiles"]) == 6
    assert {profile["hobby"]["en"] for profile in payload["demoProfiles"]} == {
        "Watercolour painting"
    }
    assert {profile["candidateId"] for profile in payload["demoProfiles"]}.isdisjoint(
        {"syn_partner_0002", "syn_partner_0003", "syn_requester_0001"}
    )
    result = payload["results"][0]
    assert result["candidateId"] == "syn_partner_0001"
    assert result["candidateType"] == "partner"
    assert result["synthetic"] is True
    assert result["score"] == sum(factor["points"] for factor in result["factorBreakdown"])
    assert len(result["reasons"]) == 3
    assert app.state.profile_repository.profiles == stores_before["profile"]
    assert app.state.journey_repository.journeys == stores_before["journey"]
    assert app.state.integration_call_counts == {"ai": 0, "paid": 0}

    forbidden = {
        "uid",
        "email",
        "city",
        "cityCode",
        "availability",
        "block",
        "rejection",
        "matchingConsent",
        "transcript",
        "rawText",
        "accessibility",
        "activityHistory",
        "credentials",
        "rawAudio",
        "seed",
    }
    assert forbidden.isdisjoint(result)
    assert all(forbidden.isdisjoint(profile) for profile in payload["demoProfiles"])


def test_kathak_profile_returns_an_explainable_synthetic_mentor() -> None:
    client, _ = client_with_profile(
        {
            **PROFILE,
            "hobby": "Kathak",
            "goal": "Build a regular practice routine",
            "language": "English and Hindi",
            "format": "At home · individual",
            "city": "",
        }
    )

    response = client.get(
        "/api/v1/recommendations?type=mentor",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "matched"
    assert payload["recommendationType"] == "mentor"
    assert payload["results"][0]["candidateType"] == "mentor"
    assert payload["results"][0]["hobby"] == {"en": "Kathak", "hi": "कथक"}
    assert len(payload["results"][0]["reasons"]) == 3


def test_query_boundary_rejects_unsupported_type_and_unapproved_inputs() -> None:
    client, _ = client_with_profile()

    unsupported = client.get(
        "/api/v1/recommendations?type=circle",
        headers=AUTH_HEADERS,
    )
    injected = client.get(
        "/api/v1/recommendations?type=partner&uid=someone&hobby=drawing",
        headers=AUTH_HEADERS,
    )

    assert unsupported.status_code == 422
    assert unsupported.json()["detail"]["code"] == "unsupported_recommendation_type"
    assert injected.status_code == 422
    assert injected.json()["detail"]["code"] == "unsupported_recommendation_query"


def test_unknown_hobby_no_match_and_unavailable_states_reveal_no_candidate_detail() -> None:
    unknown_client, _ = client_with_profile({**PROFILE, "hobby": "Astronomy"})
    unknown = unknown_client.get(
        "/api/v1/recommendations?type=partner",
        headers=AUTH_HEADERS,
    )
    assert unknown.status_code == 200
    assert unknown.json()["status"] == "no_matches"
    assert unknown.json()["emptyReason"] == "hobby_not_in_catalog"
    assert unknown.json()["results"] == []

    client, app = client_with_profile()
    dataset = app.state.recommendation_repository.dataset
    all_inactive = [
        learner.model_copy(update={"active": False}) for learner in dataset.learners
    ]
    app.state.recommendation_repository.dataset = dataset.model_copy(
        update={"learners": all_inactive},
    )
    no_match = client.get(
        "/api/v1/recommendations?type=partner",
        headers=AUTH_HEADERS,
    )
    assert no_match.status_code == 200
    assert no_match.json()["emptyReason"] == "no_eligible_candidate"
    assert "filtered" not in no_match.text.lower()
    assert "block" not in no_match.text.lower()

    app.state.recommendation_repository.dataset = None
    unavailable = client.get(
        "/api/v1/recommendations?type=partner",
        headers=AUTH_HEADERS,
    )
    assert unavailable.status_code == 503
    assert unavailable.json()["detail"]["code"] == "recommendations_unavailable"


def test_production_recommendations_fail_closed_without_using_the_synthetic_adapter() -> None:
    class AvailableCostControls:
        def read(self):
            return type("Controls", (), {"maintenance_mode": False})()

    class UnavailableRecommendationRepository:
        def get_dataset(self):
            raise OperationalDataUnavailable("operational data unavailable")

    profile_repository = InMemoryProfileRepository()
    profile_repository.save_profile(
        "firebase-user",
        LearningWishProfile.model_validate(PROFILE),
    )
    recommendation_repository = UnavailableRecommendationRepository()
    app = create_app(
        Settings(
            app_env="production",
            adapter_mode="production",
            firebase_project_id="sakhicircle-production",
            firebase_app_id="web-app",
            firestore_database_id="(default)",
        ),
        profile_repository=profile_repository,
        journey_repository=InMemoryJourneyRepository(),
        recommendation_repository=recommendation_repository,
        cost_control_reader=AvailableCostControls(),
        quota_service=QuotaService(InMemoryQuotaCounterStore()),
    )
    client = TestClient(app)
    headers = {
        "Authorization": "Bearer valid-id-token",
        "X-Firebase-AppCheck": "valid-app-check-token",
    }
    with (
        patch(
            "app.auth._verify_firebase_token",
            return_value=AuthenticatedUser(
                uid="firebase-user",
                displayName="SakhiCircle member",
                roles=["learner"],
                synthetic=False,
            ),
        ),
        patch("app.auth.firebase_app_check.verify_token", return_value={"app_id": "web-app"}),
    ):
        response = client.get("/api/v1/recommendations?type=partner", headers=headers)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "recommendations_configuration_required"
    assert app.state.recommendation_repository is recommendation_repository
