from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: Literal["development", "test", "production"] = "development"
    demo_mode: bool = False
    adapter_mode: Literal["deterministic", "firebase_emulator", "production"] = "deterministic"
    journey_adapter_mode: Literal["deterministic", "gemini_adk"] = "deterministic"
    journey_attempt_timeout_seconds: float = Field(default=10, gt=0, le=10)
    paid_api_calls_enabled: bool = False
    gemini_model: str = "gemini-3.7-flash"
    gemini_api_key: SecretStr | None = None
    firebase_project_id: str | None = None
    firebase_app_id: str | None = None
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SAKHI_",
        extra="ignore",
        case_sensitive=False,
    )

    @model_validator(mode="after")
    def fail_closed_in_production(self) -> "Settings":
        if self.app_env != "production" and self.paid_api_calls_enabled:
            raise ValueError("Paid API calls cannot be enabled outside production")
        if self.app_env == "production" and self.demo_mode:
            raise ValueError("Demo mode cannot be enabled in production")
        if self.app_env == "production" and self.adapter_mode != "production":
            raise ValueError("Production APP_ENV requires production adapters")
        if self.app_env == "production" and not self.firebase_project_id:
            raise ValueError("SAKHI_FIREBASE_PROJECT_ID is required in production")
        if self.app_env == "production" and not self.firebase_app_id:
            raise ValueError("SAKHI_FIREBASE_APP_ID is required in production")
        if self.adapter_mode == "production" and self.app_env != "production":
            raise ValueError("Production adapters require production APP_ENV")
        if self.app_env == "production" and self.journey_adapter_mode == "gemini_adk":
            if not self.paid_api_calls_enabled:
                raise ValueError("Gemini journeys require SAKHI_PAID_API_CALLS_ENABLED=true")
            if self.gemini_api_key is None:
                raise ValueError("SAKHI_GEMINI_API_KEY is required for Gemini journeys")
        return self
