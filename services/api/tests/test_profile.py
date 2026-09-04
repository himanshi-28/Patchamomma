from fastapi.testclient import TestClient

from app.config import Settings
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
    "matchingConsent": False,
    "city": "Pune",
}


def test_profile_write_requires_authentication() -> None:
    client = TestClient(create_app(Settings(app_env="test", demo_mode=True)))

    response = client.put("/api/v1/profile", json=PROFILE)

    assert response.status_code == 401


def test_confirmed_profile_saves_only_reviewed_structured_fields() -> None:
    app = create_app(Settings(app_env="test", demo_mode=True))
    client = TestClient(app)

    response = client.put("/api/v1/profile", headers=AUTH_HEADERS, json=PROFILE)

    assert response.status_code == 200
    assert response.json() == {"status": "saved", "profile": PROFILE}
    assert (
        app.state.profile_repository.get_profile("demo-meera").model_dump(by_alias=True)
        == PROFILE
    )


def test_profile_boundary_rejects_transcript_raw_audio_and_missing_consent() -> None:
    client = TestClient(create_app(Settings(app_env="test", demo_mode=True)))

    with_transcript = client.put(
        "/api/v1/profile",
        headers=AUTH_HEADERS,
        json={**PROFILE, "transcript": "private words"},
    )
    with_audio = client.put(
        "/api/v1/profile",
        headers=AUTH_HEADERS,
        json={**PROFILE, "rawAudio": "bytes"},
    )
    without_consent = client.put(
        "/api/v1/profile",
        headers=AUTH_HEADERS,
        json={**PROFILE, "planConsent": False},
    )

    assert with_transcript.status_code == 422
    assert with_audio.status_code == 422
    assert without_consent.status_code == 422


def test_profile_accepts_omitted_experience_and_first_goal() -> None:
    app = create_app(Settings(app_env="test", demo_mode=True))
    client = TestClient(app)
    optional_profile = {**PROFILE, "experience": "", "goal": ""}

    response = client.put("/api/v1/profile", headers=AUTH_HEADERS, json=optional_profile)

    assert response.status_code == 200
    assert response.json()["profile"]["experience"] == ""
    assert response.json()["profile"]["goal"] == ""
