from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app


def test_protected_session_rejects_missing_token() -> None:
    app = create_app(Settings(app_env="test", demo_mode=True))
    response = TestClient(app).get("/api/v1/auth/session")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"


def test_demo_token_is_accepted_only_when_demo_mode_is_enabled() -> None:
    demo_client = TestClient(create_app(Settings(app_env="test", demo_mode=True)))
    production_client = TestClient(
        create_app(
            Settings(
                app_env="production",
                demo_mode=False,
                adapter_mode="production",
                firebase_project_id="sakhicircle-production",
                firebase_app_id="web-app",
                firestore_database_id="(default)",
            )
        )
    )
    headers = {"Authorization": "Bearer demo-learner-token"}

    demo_response = demo_client.get("/api/v1/auth/session", headers=headers)
    production_response = production_client.get("/api/v1/auth/session", headers=headers)

    assert demo_response.status_code == 200
    assert demo_response.json() == {
        "uid": "demo-meera",
        "displayName": "Meera Sharma",
        "roles": ["learner"],
        "synthetic": True,
    }
    assert production_response.status_code == 401


def test_production_requires_app_check_in_addition_to_a_valid_id_token() -> None:
    client = TestClient(
        create_app(
            Settings(
                app_env="production",
                adapter_mode="production",
                firebase_project_id="sakhicircle-production",
                firebase_app_id="web-app",
                firestore_database_id="(default)",
            )
        )
    )

    with patch(
        "app.auth._verify_firebase_token",
        return_value={
            "uid": "firebase-user",
            "displayName": "SakhiCircle member",
            "roles": ["learner"],
            "synthetic": False,
        },
    ):
        response = client.get(
            "/api/v1/auth/session",
            headers={"Authorization": "Bearer valid-id-token"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "App verification required"
    assert "valid-id-token" not in response.text


def test_production_accepts_verified_id_and_app_check_tokens() -> None:
    client = TestClient(
        create_app(
            Settings(
                app_env="production",
                adapter_mode="production",
                firebase_project_id="sakhicircle-production",
                firebase_app_id="web-app",
                firestore_database_id="(default)",
            )
        )
    )
    headers = {
        "Authorization": "Bearer valid-id-token",
        "X-Firebase-AppCheck": "valid-app-check-token",
    }

    with (
        patch(
            "app.auth._verify_firebase_token",
            return_value={
                "uid": "firebase-user",
                "displayName": "SakhiCircle member",
                "roles": ["learner"],
                "synthetic": False,
            },
        ),
        patch("app.auth.firebase_app_check.verify_token", return_value={"app_id": "web-app"}) as verify,
    ):
        response = client.get("/api/v1/auth/session", headers=headers)

    assert response.status_code == 200
    assert response.json()["uid"] == "firebase-user"
    verify.assert_called_once_with("valid-app-check-token")


def test_invalid_app_check_token_returns_403_without_token_detail() -> None:
    client = TestClient(
        create_app(
            Settings(
                app_env="production",
                adapter_mode="production",
                firebase_project_id="sakhicircle-production",
                firebase_app_id="web-app",
                firestore_database_id="(default)",
            )
        )
    )
    headers = {
        "Authorization": "Bearer valid-id-token",
        "X-Firebase-AppCheck": "copied-invalid-app-check-token",
    }

    with (
        patch(
            "app.auth._verify_firebase_token",
            return_value={
                "uid": "firebase-user",
                "displayName": "SakhiCircle member",
                "roles": ["learner"],
                "synthetic": False,
            },
        ),
        patch("app.auth.firebase_app_check.verify_token", side_effect=ValueError("bad token")),
    ):
        response = client.get("/api/v1/auth/session", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "App verification required"
    assert "copied-invalid-app-check-token" not in response.text


def test_production_configuration_fails_closed() -> None:
    with pytest.raises(ValidationError, match="Production APP_ENV requires production adapters"):
        Settings(
            app_env="production",
            firebase_project_id="sakhicircle-production",
            firebase_app_id="web-app",
        )

    with pytest.raises(ValidationError, match="SAKHI_FIREBASE_PROJECT_ID is required"):
        Settings(app_env="production", adapter_mode="production")

    with pytest.raises(ValidationError, match="Demo mode cannot be enabled in production"):
        Settings(
            app_env="production",
            adapter_mode="production",
            demo_mode=True,
            firebase_project_id="sakhicircle-production",
            firebase_app_id="web-app",
        )

    with pytest.raises(ValidationError, match="Production adapters require production"):
        Settings(
            app_env="development",
            adapter_mode="production",
            firebase_project_id="sakhicircle-production",
            firebase_app_id="web-app",
        )
