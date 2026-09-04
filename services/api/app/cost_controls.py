from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any, Literal, Protocol

import firebase_admin
from firebase_admin import firestore
from pydantic import BaseModel, ConfigDict, Field, field_validator

COST_CONTROLS_SCHEMA_VERSION = "cost-controls-v1.0.0"
GEMINI_DEPLOYMENT_DAILY_MAXIMUM = 20
COST_CONTROLS_COLLECTION = "ops_config"
COST_CONTROLS_DOCUMENT = "cost_controls_v1"


class CostControlStateUnavailable(RuntimeError):
    """The production cost-control document cannot be trusted."""


class CostControlState(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal["cost-controls-v1.0.0"] = Field(alias="schemaVersion")
    gemini_project_daily_allowance: int = Field(
        alias="geminiProjectDailyAllowance",
        ge=0,
        le=GEMINI_DEPLOYMENT_DAILY_MAXIMUM,
    )
    maintenance_mode: bool = Field(alias="maintenanceMode")
    updated_at: datetime = Field(alias="updatedAt")

    @field_validator("updated_at")
    @classmethod
    def require_server_timestamp_with_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("updatedAt must include a timezone")
        return value.astimezone(UTC)


class CostControlSource(Protocol):
    def read(self) -> object: ...


class FirestoreCostControlSource:
    """Read-only access to the one approved production control document."""

    def __init__(self, *, project_id: str, client: Any | None = None) -> None:
        self._project_id = project_id
        self._client = client
        self._client_lock = Lock()

    def _firestore_client(self) -> Any:
        if self._client is not None:
            return self._client
        with self._client_lock:
            if self._client is None:
                try:
                    app = firebase_admin.get_app()
                except ValueError:
                    app = firebase_admin.initialize_app(options={"projectId": self._project_id})
                if app.project_id != self._project_id:
                    raise CostControlStateUnavailable(
                        "Firebase app does not match the configured project"
                    )
                self._client = firestore.client(app=app)
        return self._client

    def read(self) -> Mapping[str, object] | None:
        snapshot = (
            self._firestore_client()
            .collection(COST_CONTROLS_COLLECTION)
            .document(COST_CONTROLS_DOCUMENT)
            .get()
        )
        if not snapshot.exists:
            return None
        return snapshot.to_dict()


class CachedCostControlReader:
    def __init__(
        self,
        source: CostControlSource,
        *,
        clock: Callable[[], datetime] | None = None,
        max_age: timedelta = timedelta(seconds=60),
    ) -> None:
        if max_age > timedelta(seconds=60) or max_age < timedelta(0):
            raise ValueError("Cost-control cache age must be between 0 and 60 seconds")
        self._source = source
        self._clock = clock or (lambda: datetime.now(UTC))
        self._max_age = max_age
        self._cached: CostControlState | None = None
        self._cached_at: datetime | None = None
        self._lock = Lock()

    def read(self) -> CostControlState:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise CostControlStateUnavailable("Cost-control server clock is invalid")
        now = now.astimezone(UTC)
        with self._lock:
            if (
                self._cached is not None
                and self._cached_at is not None
                and timedelta(0) <= now - self._cached_at <= self._max_age
            ):
                return self._cached
            try:
                raw = self._source.read()
                if raw is None:
                    raise ValueError("Cost-control document is missing")
                state = CostControlState.model_validate(raw)
            except Exception as error:
                raise CostControlStateUnavailable(
                    "Production cost controls are unavailable"
                ) from error
            self._cached = state
            self._cached_at = now
            return state
