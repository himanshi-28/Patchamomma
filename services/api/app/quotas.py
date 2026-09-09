import hashlib
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from threading import Lock
from typing import Any, Literal, Protocol
from zoneinfo import ZoneInfo

import firebase_admin
from firebase_admin import firestore

from .cost_controls import GEMINI_DEPLOYMENT_DAILY_MAXIMUM

INDIA_TIME_ZONE = ZoneInfo("Asia/Kolkata")
QUOTA_COUNTER_SCHEMA_VERSION = "quota-counter-v1.0.0"
QUOTA_COUNTER_COLLECTION = "runtime_quota_counters_v1"
COUNTER_TTL = timedelta(days=7)


class QuotaStoreUnavailable(RuntimeError):
    """The authoritative persistent counter store could not reserve capacity."""


class QuotaExceeded(RuntimeError):
    def __init__(self, *, code: str, retry_after: int) -> None:
        super().__init__(code)
        self.code = code
        self.retry_after = max(1, retry_after)


WindowKind = Literal["rolling", "india_day"]


@dataclass(frozen=True)
class QuotaReservation:
    quota_name: str
    scope_kind: Literal["subject", "project"]
    scope_key: str
    limit: int
    window_kind: WindowKind
    failure_code: str
    window_seconds: int | None = None
    idempotency_key: str | None = None

    def __post_init__(self) -> None:
        if not self.scope_key:
            raise ValueError("Quota scope cannot be empty")
        if self.limit < 0:
            raise ValueError("Quota limit cannot be negative")
        if self.window_kind == "rolling" and not self.window_seconds:
            raise ValueError("Rolling quota requires a positive window")
        if self.window_kind == "india_day" and self.window_seconds is not None:
            raise ValueError("India-day quota cannot set rolling seconds")


class QuotaCounterStore(Protocol):
    def reserve(self, reservations: Sequence[QuotaReservation], *, now: datetime) -> None: ...


def _server_utc(now: datetime) -> datetime:
    if now.tzinfo is None or now.utcoffset() is None:
        raise QuotaStoreUnavailable("Quota server clock is invalid")
    return now.astimezone(UTC)


def _india_date(now: datetime) -> date:
    return now.astimezone(INDIA_TIME_ZONE).date()


def _seconds_until_india_midnight(now: datetime) -> int:
    local_now = now.astimezone(INDIA_TIME_ZONE)
    next_midnight = datetime.combine(
        local_now.date() + timedelta(days=1),
        time.min,
        tzinfo=INDIA_TIME_ZONE,
    )
    return max(1, math.ceil((next_midnight - local_now).total_seconds()))


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _document_id(reservation: QuotaReservation, now: datetime) -> str:
    parts = [reservation.quota_name, reservation.scope_kind, _digest(reservation.scope_key)]
    if reservation.window_kind == "india_day":
        parts.append(_india_date(now).isoformat())
    return _digest(":".join(parts))


def _normalized_timestamps(raw: object) -> list[datetime]:
    if not isinstance(raw, list):
        return []
    normalized: list[datetime] = []
    for value in raw:
        if isinstance(value, datetime) and value.tzinfo is not None:
            normalized.append(value.astimezone(UTC))
    return normalized


def _normalized_keys(raw: object) -> set[str]:
    if not isinstance(raw, list):
        return set()
    return {value for value in raw if isinstance(value, str)}


def _plan_reservation(
    raw: Mapping[str, object] | None,
    reservation: QuotaReservation,
    *,
    now: datetime,
) -> dict[str, object]:
    document = dict(raw or {})
    idempotency_hash = _digest(reservation.idempotency_key) if reservation.idempotency_key else None
    common = {
        "schemaVersion": QUOTA_COUNTER_SCHEMA_VERSION,
        "quotaName": reservation.quota_name,
        "scopeKind": reservation.scope_kind,
        "scopeHash": _digest(reservation.scope_key),
        "windowKind": reservation.window_kind,
        "expiresAt": now + COUNTER_TTL,
    }
    if document:
        expected_identity = {
            "schemaVersion": QUOTA_COUNTER_SCHEMA_VERSION,
            "quotaName": reservation.quota_name,
            "scopeKind": reservation.scope_kind,
            "scopeHash": _digest(reservation.scope_key),
            "windowKind": reservation.window_kind,
        }
        if any(document.get(key) != value for key, value in expected_identity.items()):
            raise QuotaStoreUnavailable("Persistent quota counter identity is invalid")

    if reservation.window_kind == "rolling":
        assert reservation.window_seconds is not None
        raw_timestamps = document.get("acceptedAt", [])
        if not isinstance(raw_timestamps, list) or any(
            not isinstance(value, datetime) or value.tzinfo is None for value in raw_timestamps
        ):
            raise QuotaStoreUnavailable("Persistent rolling counter is invalid")
        cutoff = now - timedelta(seconds=reservation.window_seconds)
        accepted_at = [
            timestamp
            for timestamp in _normalized_timestamps(document.get("acceptedAt"))
            if timestamp > cutoff
        ]
        if reservation.limit == 0:
            raise QuotaExceeded(
                code=reservation.failure_code,
                retry_after=reservation.window_seconds,
            )
        if len(accepted_at) >= reservation.limit:
            retry_at = min(accepted_at) + timedelta(seconds=reservation.window_seconds)
            raise QuotaExceeded(
                code=reservation.failure_code,
                retry_after=math.ceil((retry_at - now).total_seconds()),
            )
        accepted_at.append(now)
        return {**common, "acceptedAt": accepted_at}

    idempotency_keys = _normalized_keys(document.get("idempotencyKeys"))
    raw_keys = document.get("idempotencyKeys", [])
    if not isinstance(raw_keys, list) or any(not isinstance(value, str) for value in raw_keys):
        raise QuotaStoreUnavailable("Persistent daily counter idempotency state is invalid")
    if document and document.get("indiaDate") != _india_date(now).isoformat():
        raise QuotaStoreUnavailable("Persistent daily counter date is invalid")
    if idempotency_hash is not None and idempotency_hash in idempotency_keys:
        return document
    count = document.get("count", 0)
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise QuotaStoreUnavailable("Persistent quota counter is invalid")
    if count >= reservation.limit:
        raise QuotaExceeded(
            code=reservation.failure_code,
            retry_after=_seconds_until_india_midnight(now),
        )
    if idempotency_hash is not None:
        idempotency_keys.add(idempotency_hash)
    return {
        **common,
        "indiaDate": _india_date(now).isoformat(),
        "count": count + 1,
        "idempotencyKeys": sorted(idempotency_keys),
    }


def _plan_all(
    documents: Mapping[str, Mapping[str, object]],
    reservations: Sequence[QuotaReservation],
    *,
    now: datetime,
) -> dict[str, dict[str, object]]:
    planned = {key: dict(value) for key, value in documents.items()}
    for reservation in reservations:
        document_id = _document_id(reservation, now)
        planned[document_id] = _plan_reservation(
            planned.get(document_id),
            reservation,
            now=now,
        )
    return planned


class InMemoryQuotaCounterStore:
    """Deterministic shared fake with the same atomic reservation rules as Firestore."""

    def __init__(self) -> None:
        self._documents: dict[str, dict[str, object]] = {}
        self._lock = Lock()

    def reserve(self, reservations: Sequence[QuotaReservation], *, now: datetime) -> None:
        checked_now = _server_utc(now)
        with self._lock:
            self._documents = _plan_all(
                self._documents,
                reservations,
                now=checked_now,
            )


class FirestoreQuotaCounterStore:
    """Transactionally reserves subject and project capacity in persistent Firestore."""

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
                    raise QuotaStoreUnavailable(
                        "Firebase app does not match the configured project"
                    )
                self._client = firestore.client(app=app)
        return self._client

    def reserve(self, reservations: Sequence[QuotaReservation], *, now: datetime) -> None:
        checked_now = _server_utc(now)
        try:
            client = self._firestore_client()
            references = {
                _document_id(reservation, checked_now): client.collection(
                    QUOTA_COUNTER_COLLECTION
                ).document(_document_id(reservation, checked_now))
                for reservation in reservations
            }
            transaction = client.transaction()

            @firestore.transactional
            def reserve_in_transaction(active_transaction: Any) -> None:
                documents: dict[str, Mapping[str, object]] = {}
                for document_id, reference in references.items():
                    snapshot = reference.get(transaction=active_transaction)
                    if snapshot.exists:
                        documents[document_id] = snapshot.to_dict() or {}
                planned = _plan_all(documents, reservations, now=checked_now)
                for document_id, document in planned.items():
                    active_transaction.set(references[document_id], document)

            reserve_in_transaction(transaction)
        except QuotaExceeded:
            raise
        except QuotaStoreUnavailable:
            raise
        except Exception as error:
            raise QuotaStoreUnavailable("Persistent quota reservation failed") from error


class QuotaService:
    def __init__(
        self,
        store: QuotaCounterStore,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store
        self._clock = clock or (lambda: datetime.now(UTC))

    def _reserve(self, reservations: Sequence[QuotaReservation]) -> None:
        self._store.reserve(reservations, now=_server_utc(self._clock()))

    def reserve_general_request(self, subject_key: str) -> None:
        self._reserve(
            [
                QuotaReservation(
                    quota_name="protected_api",
                    scope_kind="subject",
                    scope_key=subject_key,
                    limit=60,
                    window_kind="rolling",
                    window_seconds=60,
                    failure_code="protected_api_quota_exceeded",
                )
            ]
        )

    def reserve_youtube_search(self, subject_key: str, *, idempotency_key: str) -> None:
        self._reserve(
            [
                QuotaReservation(
                    quota_name="youtube_search",
                    scope_kind="subject",
                    scope_key=subject_key,
                    limit=5,
                    window_kind="india_day",
                    idempotency_key=idempotency_key,
                    failure_code="youtube_subject_daily_quota_exceeded",
                ),
                QuotaReservation(
                    quota_name="youtube_search",
                    scope_kind="project",
                    scope_key="sakhicircle-youtube-project",
                    limit=20,
                    window_kind="india_day",
                    idempotency_key=idempotency_key,
                    failure_code="youtube_project_daily_quota_exceeded",
                ),
            ]
        )

    def reserve_analytics_event(self, subject_key: str, event_id: str) -> None:
        self._reserve(
            [
                QuotaReservation(
                    quota_name="analytics_event",
                    scope_kind="subject",
                    scope_key=subject_key,
                    limit=20,
                    window_kind="india_day",
                    idempotency_key=event_id,
                    failure_code="analytics_quota_exceeded",
                ),
                QuotaReservation(
                    quota_name="analytics_event",
                    scope_kind="project",
                    scope_key="checkpoint_project",
                    limit=500,
                    window_kind="india_day",
                    idempotency_key=event_id,
                    failure_code="analytics_quota_exceeded",
                ),
            ]
        )

    def reserve_recommendation(self, subject_key: str) -> None:
        self._reserve(
            [
                QuotaReservation(
                    quota_name="recommendation",
                    scope_kind="subject",
                    scope_key=subject_key,
                    limit=20,
                    window_kind="india_day",
                    failure_code="recommendation_quota_exceeded",
                ),
                QuotaReservation(
                    quota_name="recommendation",
                    scope_kind="project",
                    scope_key="checkpoint_project",
                    limit=500,
                    window_kind="india_day",
                    failure_code="recommendation_quota_exceeded",
                ),
            ]
        )

    def reserve_gemini_workflow(
        self,
        subject_key: str,
        *,
        project_daily_allowance: int,
        subject_rolling_allowance: int = 3,
    ) -> None:
        if not 0 <= project_daily_allowance <= GEMINI_DEPLOYMENT_DAILY_MAXIMUM:
            raise ValueError(
                "Gemini allowance cannot exceed the immutable deployment maximum of 20"
            )
        if not 0 <= subject_rolling_allowance <= GEMINI_DEPLOYMENT_DAILY_MAXIMUM:
            raise ValueError(
                "Gemini subject allowance cannot exceed the immutable deployment maximum of 20"
            )
        self._reserve(
            [
                QuotaReservation(
                    quota_name="gemini_workflow",
                    scope_kind="subject",
                    scope_key=subject_key,
                    limit=subject_rolling_allowance,
                    window_kind="rolling",
                    window_seconds=24 * 60 * 60,
                    failure_code="gemini_quota_exceeded",
                ),
                QuotaReservation(
                    quota_name="gemini_workflow",
                    scope_kind="project",
                    scope_key="checkpoint_project",
                    limit=project_daily_allowance,
                    window_kind="india_day",
                    failure_code="gemini_quota_exceeded",
                ),
            ]
        )
