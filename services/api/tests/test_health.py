from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_reports_non_sensitive_service_state() -> None:
    app = create_app(Settings(app_env="test", demo_mode=True))
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "sakhicircle-api",
        "environment": "test",
    }
    assert "secret" not in response.text.lower()
    assert "key" not in response.text.lower()


def test_readiness_reports_deterministic_unpaid_local_adapters() -> None:
    app = create_app(
        Settings(
            app_env="test",
            demo_mode=True,
            adapter_mode="deterministic",
            paid_api_calls_enabled=False,
        )
    )
    response = TestClient(app).get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "sakhicircle-api",
        "environment": "test",
        "adapterMode": "deterministic",
        "paidApiCallsEnabled": False,
    }
