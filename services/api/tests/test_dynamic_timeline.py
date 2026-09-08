from datetime import date

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
    "planWeeks": 6,
}


def test_selected_six_week_timeline_controls_deterministic_journey_length() -> None:
    app = create_app(Settings(app_env="test", demo_mode=True))
    client = TestClient(app)
    saved = client.put("/api/v1/profile", headers=AUTH_HEADERS, json=PROFILE)

    assert saved.status_code == 200
    response = client.post(
        "/api/v1/journeys",
        headers=AUTH_HEADERS,
        json={"startsOn": date(2026, 9, 8).isoformat()},
    )

    assert response.status_code == 200
    journey = response.json()
    assert journey["schemaVersion"] == "1.1.0"
    assert len(journey["weeks"]) == 6
    assert sum(len(week["activities"]) for week in journey["weeks"]) == 42
    assert journey["weeks"][-1]["weekNumber"] == 6
