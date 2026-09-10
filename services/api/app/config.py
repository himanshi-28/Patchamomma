from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: Literal["development", "test", "production"] = "development"
    demo_mode: bool = False
    adapter_mode: Literal["deterministic", "firebase_emulator", "production"] = "deterministic"
    journey_adapter_mode: Literal["deterministic", "gemini_adk"] = "deterministic"
    journey_attempt_timeout_seconds: float = Field(default=90, gt=0, le=90)
    profile_extraction_timeout_seconds: float = Field(default=10, gt=0, le=10)
    paid_api_calls_enabled: bool = False
    gemini_model: str = "gemini-3.7-flash"
    journey_gemini_model: str = "gemini-2.5-flash"
    video_guide_gemini_model: str = "gemini-2.5-flash-lite"
    youtube_discovery_enabled: bool = False
    youtube_api_key: SecretStr | None = None
    youtube_timeout_seconds: float = Field(default=8, gt=0, le=15)
    video_enrichment_timeout_seconds: float = Field(default=30, gt=0, le=30)
    privacy_policy_url: str | None = None
    gemini_backend: Literal["developer_api", "vertex_ai"] = "developer_api"
    gemini_location: str = "global"
    gemini_api_key: SecretStr | None = None
    firebase_project_id: str | None = None
    firebase_app_id: str | None = None
    firestore_database_id: str | None = None
    analytics_location: str | None = None
    analytics_private_dataset_id: str | None = None
    analytics_table_id: str | None = None
    analytics_reporting_dataset_id: str | None = None
    analytics_reporting_view_id: str | None = None
    analytics_queue_id: str | None = None
    analytics_task_service_account: str | None = None
    analytics_task_audience: str | None = None
    analytics_hmac_secret_name: str | None = None
    analytics_hmac_secret_versions: list[str] = Field(default_factory=list)
    analytics_current_hmac_secret_version: str | None = None
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SAKHI_",
        extra="ignore",
        case_sensitive=False,
    )

    @model_validator(mode="after")
    def fail_closed_in_production(self) -> "Settings":
        if self.youtube_discovery_enabled and self.youtube_api_key is None:
            raise ValueError("SAKHI_YOUTUBE_API_KEY is required when YouTube discovery is enabled")
        if (
            self.app_env == "production"
            and self.youtube_discovery_enabled
            and not self.privacy_policy_url
        ):
            raise ValueError("SAKHI_PRIVACY_POLICY_URL is required for YouTube discovery")
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
            if self.gemini_backend == "developer_api" and self.gemini_api_key is None:
                raise ValueError("SAKHI_GEMINI_API_KEY is required for Gemini journeys")
        return self
