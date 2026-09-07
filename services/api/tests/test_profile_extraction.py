from fastapi.testclient import TestClient

from app.auth import AuthenticatedUser, require_user
from app.config import Settings
from app.main import create_app
from app.profile_extraction import (
    GoogleProfileExtractor,
    ProfileExtractionFields,
    ProfileExtractionResult,
    ProfileExtractionUnavailable,
)

AUTH_HEADERS = {"Authorization": "Bearer demo-learner-token"}


class ScriptedExtractor:
    def __init__(self, outcome: ProfileExtractionResult | Exception) -> None:
        self.outcome = outcome
        self.requests = []

    async def extract(self, request):
        self.requests.append(request)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def fields() -> ProfileExtractionFields:
    return ProfileExtractionFields(
        hobby="Kathak",
        experience="New to this",
        goal="Perform a short piece",
        availability="30 minutes · 4 days a week",
        language="English and Hindi",
        accessibility="No support needed right now",
        format="At home · individual",
        city="",
    )


def test_google_extractor_uses_the_json_schema_transport_supported_by_gemini() -> None:
    config = GoogleProfileExtractor.build_generation_config()

    assert config.response_schema is None
    assert config.response_json_schema == ProfileExtractionFields.model_json_schema()


def test_authenticated_ai_extraction_returns_strict_suggestions_without_persistence() -> None:
    extractor = ScriptedExtractor(ProfileExtractionResult(source="gemini", fields=fields()))
    app = create_app(
        Settings(app_env="test", demo_mode=True, journey_adapter_mode="gemini_adk"),
        profile_extractor=extractor,
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/profile/extractions",
        headers=AUTH_HEADERS,
        json={"transcript": "I want to learn Kathak.", "locale": "en"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "source": "gemini",
        "fields": fields().model_dump(by_alias=True),
    }
    assert extractor.requests[0].transcript == "I want to learn Kathak."
    assert app.state.profile_repository.get_profile("demo-meera") is None
    assert app.state.integration_call_counts == {"ai": 1, "paid": 0}


def test_extraction_requires_auth_and_rejects_audio_or_unknown_fields() -> None:
    extractor = ScriptedExtractor(ProfileExtractionResult(source="gemini", fields=fields()))
    app = create_app(Settings(app_env="test", demo_mode=True), profile_extractor=extractor)
    client = TestClient(app)

    unauthenticated = client.post(
        "/api/v1/profile/extractions",
        json={"transcript": "I want to learn Kathak.", "locale": "en"},
    )
    with_audio = client.post(
        "/api/v1/profile/extractions",
        headers=AUTH_HEADERS,
        json={
            "transcript": "I want to learn Kathak.",
            "locale": "en",
            "rawAudio": "forbidden",
        },
    )

    assert unauthenticated.status_code == 401
    assert with_audio.status_code == 422
    assert extractor.requests == []


def test_unavailable_ai_uses_private_deterministic_fallback() -> None:
    extractor = ScriptedExtractor(ProfileExtractionUnavailable("provider unavailable"))
    app = create_app(
        Settings(app_env="test", demo_mode=True, journey_adapter_mode="gemini_adk"),
        profile_extractor=extractor,
    )
    app.dependency_overrides[require_user] = lambda: AuthenticatedUser(
        uid="member-1",
        displayName="Member",
        roles=["learner"],
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/profile/extractions",
        headers=AUTH_HEADERS,
        json={
            "transcript": (
                "I want to learn pottery so I can make diyas. "
                "I have 15 minutes, three days a week."
            ),
            "locale": "en",
        },
    )

    assert response.status_code == 200
    assert response.json()["source"] == "deterministic_fallback"
    assert response.json()["fields"]["hobby"] == "Pottery"
    assert response.json()["fields"]["goal"] == "Make diyas"
