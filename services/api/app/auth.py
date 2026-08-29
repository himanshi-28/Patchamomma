from typing import Annotated

import firebase_admin
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import app_check as firebase_app_check
from firebase_admin import auth as firebase_auth
from pydantic import BaseModel, ConfigDict, Field

from .config import Settings


class AuthenticatedUser(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    uid: str
    display_name: str = Field(alias="displayName")
    roles: list[str]
    synthetic: bool = False


bearer = HTTPBearer(auto_error=False)


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _verify_firebase_token(token: str, settings: Settings) -> AuthenticatedUser:
    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app(options={"projectId": settings.firebase_project_id})
        decoded = firebase_auth.verify_id_token(token, check_revoked=True)
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        ) from error

    return AuthenticatedUser(
        uid=decoded["uid"],
        displayName=decoded.get("name") or "SakhiCircle member",
        roles=decoded.get("roles") or ["learner"],
        synthetic=False,
    )


def _verify_app_check_token(token: str | None, settings: Settings) -> None:
    if settings.adapter_mode != "production":
        return

    if not token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="App verification required",
        )

    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app(options={"projectId": settings.firebase_project_id})
        decoded = firebase_app_check.verify_token(token)
        if decoded.get("app_id") != settings.firebase_app_id:
            raise ValueError("App Check token belongs to a different Firebase app")
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="App verification required",
        ) from error


def require_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    settings: Annotated[Settings, Depends(_settings)],
    app_check_token: Annotated[str | None, Header(alias="X-Firebase-AppCheck")] = None,
) -> AuthenticatedUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    token = credentials.credentials
    if token == "demo-learner-token":
        if settings.demo_mode and settings.app_env != "production":
            return AuthenticatedUser(
                uid="demo-meera",
                displayName="Meera Sharma",
                roles=["learner"],
                synthetic=True,
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    user = _verify_firebase_token(token, settings)
    _verify_app_check_token(app_check_token, settings)
    return user
