from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal, Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    field_serializer,
    model_validator,
)

ANALYTICS_SCHEMA_VERSION = "analytics-v1.0.0"
RECEIPT_LIFETIME = timedelta(hours=24)
TERMINAL_OUTBOX_TTL = timedelta(days=7)
DELETION_FENCE_TTL = timedelta(days=97)
DELIVERY_LEASE = timedelta(seconds=30)
MAX_SEALED_PAYLOAD_BYTES = 4096
INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")

EventName = Literal[
    "profile_confirmed",
    "journey_draft_created",
    "journey_confirmed",
    "recommendation_presented",
]
JourneyGenerator = Literal[
    "deterministic_fixture",
    "gemini_adk",
    "curated_fallback",
]
RecommendationType = Literal["partner", "mentor"]
RecommendationOutcome = Literal["matched", "no_matches"]
DeliveryState = Literal["queued", "leased", "written", "failed", "discarded"]


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.title() for part in tail)


class AnalyticsModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        extra="forbid",
        populate_by_name=True,
    )


class ProfileAnalyticsProperties(AnalyticsModel):
    pass


class JourneyAnalyticsProperties(AnalyticsModel):
    journey_schema_version: Literal["1.0.0"]
    generator: JourneyGenerator
    fallback_used: bool

    @model_validator(mode="after")
    def fallback_matches_generator(self) -> JourneyAnalyticsProperties:
        if self.fallback_used != (self.generator == "curated_fallback"):
            raise ValueError("fallbackUsed must agree with generator")
        return self


class RecommendationAnalyticsProperties(AnalyticsModel):
    matching_contract_version: Literal["matching-v1.0.0"]
    recommendation_type: RecommendationType
    outcome: RecommendationOutcome
    result_count: int = Field(ge=0, le=3)

    @model_validator(mode="after")
    def result_count_matches_outcome(self) -> RecommendationAnalyticsProperties:
        if self.outcome == "matched" and self.result_count == 0:
            raise ValueError("matched result requires a positive resultCount")
        if self.outcome == "no_matches" and self.result_count != 0:
            raise ValueError("no_matches result requires resultCount zero")
        return self


EventProperties = (
    ProfileAnalyticsProperties | JourneyAnalyticsProperties | RecommendationAnalyticsProperties
)


class ActionReceiptClaims(AnalyticsModel):
    schema_version: Literal["analytics-v1.0.0"] = ANALYTICS_SCHEMA_VERSION
    event_id: str = Field(
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    )
    event_name: EventName
    properties: EventProperties
    issued_at: datetime
    expires_at: datetime
    nonce: str = Field(min_length=8, max_length=120)
    subject_binding: str = Field(min_length=32, max_length=120)
    key_version: str = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def event_and_properties_agree(self) -> ActionReceiptClaims:
        valid_type = {
            "profile_confirmed": ProfileAnalyticsProperties,
            "journey_draft_created": JourneyAnalyticsProperties,
            "journey_confirmed": JourneyAnalyticsProperties,
            "recommendation_presented": RecommendationAnalyticsProperties,
        }[self.event_name]
        if not isinstance(self.properties, valid_type):
            raise TypeError("Receipt properties do not match the event name")
        if self.issued_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("Receipt timestamps must be timezone-aware")
        if self.expires_at - self.issued_at != RECEIPT_LIFETIME:
            raise ValueError("Receipt lifetime must be exactly 24 hours")
        return self


class AnalyticsReceiptRequest(AnalyticsModel):
    schema_version: Literal["analytics-v1.0.0"] = ANALYTICS_SCHEMA_VERSION
    event_id: str = Field(
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    )
    action_receipt: str = Field(min_length=1, max_length=1800)


class AnalyticsStatusResponse(AnalyticsModel):
    schema_version: Literal["analytics-v1.0.0"] = ANALYTICS_SCHEMA_VERSION
    event_id: str
    status: Literal["queued", "written", "failed", "discarded"]
    duplicate: bool


class AnalyticsRow(AnalyticsModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    event_date: date
    event_timestamp: datetime
    schema_version: Literal["analytics-v1.0.0"] = ANALYTICS_SCHEMA_VERSION
    event_name: EventName
    event_id: str
    event_key: str
    payload_hash: str
    subject_key: str
    subject_key_version: str
    environment: Literal["test", "development", "production"]
    journey_schema_version: str | None = None
    journey_generator: JourneyGenerator | None = None
    journey_fallback_used: bool | None = None
    matching_contract_version: str | None = None
    recommendation_type: RecommendationType | None = None
    recommendation_outcome: RecommendationOutcome | None = None
    result_count: int | None = None

    @field_serializer("event_date")
    def serialize_event_date(self, value: date) -> str:
        return value.isoformat()

    @field_serializer("event_timestamp")
    def serialize_event_timestamp(self, value: datetime) -> str:
        return value.isoformat()


class OutboxRecord(AnalyticsModel):
    payload_hash: str
    subject_key: str
    subject_key_version: str
    delivery_handle_hash: str
    sealed_delivery_payload: str | None
    delivery_state: DeliveryState
    lease_acquired_at: datetime | None = None
    lease_expires_at: datetime | None = None
    task_name: str
    attempt_count: int = 0
    failure_code: Literal["delivery_retry_exhausted", "sealed_payload_invalid"] | None = None
    expires_at: datetime | None = None

    _event_name: EventName | None = PrivateAttr(default=None)

    @property
    def event_name(self) -> EventName | None:
        return self._event_name


class DeliveryTask(AnalyticsModel):
    name: str
    delivery_handle: str
    max_attempts: Literal[8] = 8
    max_retry_duration: timedelta = timedelta(hours=24)
    min_backoff: timedelta = timedelta(seconds=10)
    max_backoff: timedelta = timedelta(minutes=15)

    @property
    def body(self) -> dict[str, str]:
        return {"deliveryHandle": self.delivery_handle}


class DeliveryRequest(AnalyticsModel):
    delivery_handle: str = Field(min_length=32, max_length=120)


class TaskAuthClaims(AnalyticsModel):
    issuer: str
    audience: str
    service_account: str


class DeletionFenceRecord(AnalyticsModel):
    fence_key: str
    expires_at: datetime


class IssuedAnalyticsEvent(AnalyticsModel):
    event_id: str
    event_name: EventName
    properties: dict[str, Any]
    action_receipt: str
    row: AnalyticsRow
    task: DeliveryTask


class DeliveryResult(AnalyticsModel):
    status: Literal["written", "failed", "discarded"]


class AnalyticsError(RuntimeError):
    pass


class AnalyticsConflict(AnalyticsError):
    pass


class AnalyticsReceiptError(AnalyticsError):
    pass


class SealedPayloadError(AnalyticsError):
    pass


class AnalyticsDeliveryRetry(AnalyticsError):
    pass


class AnalyticsEnqueueUnavailable(AnalyticsError):
    pass


class AnalyticsUnavailable(AnalyticsError):
    pass


class TaskAuthorizationError(AnalyticsError):
    pass


class TaskTokenVerifier(Protocol):
    def verify(self, token: str) -> TaskAuthClaims: ...


class StaticTaskTokenVerifier:
    def __init__(self, claims_by_token: Mapping[str, TaskAuthClaims]) -> None:
        self._claims_by_token = dict(claims_by_token)

    def verify(self, token: str) -> TaskAuthClaims:
        try:
            return self._claims_by_token[token]
        except KeyError as error:
            raise TaskAuthorizationError("Task authentication required") from error


def _urlsafe(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _decode_urlsafe(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


class AnalyticsKeyring:
    def __init__(
        self,
        *,
        project_id: str,
        keys: Mapping[str, bytes],
        current_version: str,
    ) -> None:
        if not keys or current_version not in keys:
            raise ValueError("The current analytics HMAC key version must be resolvable")
        if any(not value for value in keys.values()):
            raise ValueError("Analytics HMAC keys cannot be empty")
        self.project_id = project_id
        self.keys = dict(keys)
        self.current_version = current_version

    def _digest(self, version: str, domain: str, value: str) -> str:
        try:
            key = self.keys[version]
        except KeyError as error:
            raise AnalyticsReceiptError("Unknown analytics HMAC key version") from error
        message = f"sakhicircle:{domain}:v1\0{value}".encode()
        return _urlsafe(hmac.new(key, message, hashlib.sha256).digest())

    def subject_key(self, uid: str, *, version: str | None = None) -> str:
        resolved_version = version or self.current_version
        return self._digest(
            resolved_version,
            "subject",
            f"{self.project_id}:{uid}",
        )

    def subject_keys_for_deletion(self, uid: str) -> dict[str, str]:
        return {version: self.subject_key(uid, version=version) for version in self.keys}

    def event_key(self, subject_key: str, event_id: str, *, version: str) -> str:
        return self._digest(version, "event", f"{subject_key}:{event_id}")

    def task_name(self, event_key: str, *, version: str) -> str:
        return f"analytics-{self._digest(version, 'task-name', event_key)}"

    def delivery_handle(self, event_key: str, nonce: str, *, version: str) -> str:
        return self._digest(version, "delivery-handle", f"{event_key}:{nonce}")

    def delivery_handle_hash(self, handle: str, *, version: str) -> str:
        return self._digest(version, "delivery-handle-lookup", handle)

    def outbox_sealing_key(self, *, version: str) -> bytes:
        try:
            key_material = self.keys[version]
        except KeyError as error:
            raise SealedPayloadError("sealed_payload_invalid") from error
        return HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=f"sakhicircle:{self.project_id}:analytics-v1".encode(),
            info=b"sakhicircle:outbox-seal:v1",
        ).derive(key_material)

    def subject_binding(
        self,
        uid: str,
        event_id: str,
        nonce: str,
        *,
        version: str,
    ) -> str:
        return self._digest(
            version,
            "receipt-subject",
            f"{self.project_id}:{uid}:{event_id}:{nonce}",
        )

    def receipt_signature(self, encoded_claims: str, *, version: str) -> str:
        return self._digest(version, "receipt", encoded_claims)

    def deletion_fence_key(self, uid: str, *, version: str | None = None) -> str:
        resolved_version = version or self.current_version
        return self.deletion_fence_key_for_subject_key(
            self.subject_key(uid, version=resolved_version),
            version=resolved_version,
        )

    def deletion_fence_key_for_subject_key(
        self,
        subject_key: str,
        *,
        version: str,
    ) -> str:
        return self._digest(
            version,
            "deletion-fence",
            subject_key,
        )


class SealedDeliveryCodec:
    def __init__(
        self,
        keyring: AnalyticsKeyring,
        *,
        nonce_factory: Callable[[], bytes] = lambda: secrets.token_bytes(12),
    ) -> None:
        self.keyring = keyring
        self.nonce_factory = nonce_factory

    @staticmethod
    def _associated_data(
        *,
        event_key: str,
        payload_hash: str,
        delivery_handle_hash: str,
    ) -> bytes:
        return _canonical_json(
            {
                "schemaVersion": ANALYTICS_SCHEMA_VERSION,
                "eventKey": event_key,
                "payloadHash": payload_hash,
                "deliveryHandleHash": delivery_handle_hash,
            }
        )

    def seal(self, row: AnalyticsRow, *, delivery_handle_hash: str) -> str:
        version = row.subject_key_version
        nonce = self.nonce_factory()
        if len(nonce) != 12:
            raise SealedPayloadError("sealed_payload_invalid")
        associated_data = self._associated_data(
            event_key=row.event_key,
            payload_hash=row.payload_hash,
            delivery_handle_hash=delivery_handle_hash,
        )
        try:
            ciphertext = AESGCM(self.keyring.outbox_sealing_key(version=version)).encrypt(
                nonce,
                _canonical_json(row.model_dump(by_alias=True, mode="json")),
                associated_data,
            )
        except Exception as error:
            raise SealedPayloadError("sealed_payload_invalid") from error
        envelope = f"v1.{version}.{_urlsafe(nonce)}.{_urlsafe(ciphertext)}"
        if len(envelope.encode()) > MAX_SEALED_PAYLOAD_BYTES:
            raise SealedPayloadError("sealed_payload_invalid")
        return envelope

    def open(
        self,
        sealed_payload: str,
        *,
        event_key: str,
        payload_hash: str,
        delivery_handle_hash: str,
    ) -> AnalyticsRow:
        try:
            if len(sealed_payload.encode()) > MAX_SEALED_PAYLOAD_BYTES:
                raise ValueError("Oversized sealed payload")
            envelope_version, key_version, encoded_nonce, encoded_ciphertext = sealed_payload.split(
                "."
            )
            if envelope_version != "v1" or key_version not in self.keyring.keys:
                raise ValueError("Unsupported sealed payload version")
            nonce = _decode_urlsafe(encoded_nonce)
            if len(nonce) != 12:
                raise ValueError("Invalid sealed payload nonce")
            plaintext = AESGCM(self.keyring.outbox_sealing_key(version=key_version)).decrypt(
                nonce,
                _decode_urlsafe(encoded_ciphertext),
                self._associated_data(
                    event_key=event_key,
                    payload_hash=payload_hash,
                    delivery_handle_hash=delivery_handle_hash,
                ),
            )
            row = AnalyticsRow.model_validate_json(plaintext)
            if (
                row.event_key != event_key
                or row.payload_hash != payload_hash
                or row.subject_key_version != key_version
            ):
                raise ValueError("Sealed row metadata mismatch")
            return row
        except Exception as error:
            raise SealedPayloadError("sealed_payload_invalid") from error


def uuid7(now: datetime) -> str:
    milliseconds = int(now.timestamp() * 1000)
    if not 0 <= milliseconds < 1 << 48:
        raise ValueError("Timestamp is outside the UUIDv7 range")
    random_bits = int.from_bytes(secrets.token_bytes(10), "big") & ((1 << 74) - 1)
    value = milliseconds << 80
    value |= 0x7 << 76
    value |= ((random_bits >> 62) & 0xFFF) << 64
    value |= 0b10 << 62
    value |= random_bits & ((1 << 62) - 1)
    return str(UUID(int=value))


class InMemoryAnalyticsBackend:
    def __init__(self) -> None:
        self.outbox: dict[str, OutboxRecord] = {}
        self.tasks: dict[str, DeliveryTask] = {}
        self.warehouse_rows: dict[str, AnalyticsRow] = {}
        self.deletion_fences: dict[str, DeletionFenceRecord] = {}
        self.linkable_counter_records: dict[str, dict[str, Any]] = {}
        self.enqueue_count = 0
        self.network_call_count = 0
        self.paid_call_count = 0
        self.fail_next_enqueues = 0
        self.fail_next_writes = 0
        self.raise_ambiguous_after_next_insert = False
        self.lock = threading.RLock()
        self._fenced_subject_keys: set[str] = set()

    def register_occurrence(
        self,
        row: AnalyticsRow,
        record: OutboxRecord,
        task: DeliveryTask,
    ) -> tuple[AnalyticsRow, OutboxRecord, DeliveryTask, bool]:
        with self.lock:
            existing = self.outbox.get(row.event_key)
            if existing is not None:
                if existing.payload_hash != row.payload_hash:
                    raise AnalyticsConflict("event_id_conflict")
                return (
                    row,
                    existing,
                    self.tasks.get(existing.task_name, task),
                    False,
                )
            record._event_name = row.event_name
            self.outbox[row.event_key] = record
            return row, record, task, True

    def enqueue(self, task: DeliveryTask) -> None:
        with self.lock:
            if self.fail_next_enqueues:
                self.fail_next_enqueues -= 1
                raise AnalyticsEnqueueUnavailable("Analytics queue unavailable")
            if task.name not in self.tasks:
                self.tasks[task.name] = task
                self.enqueue_count += 1

    def occurrence_for_handle_hashes(
        self,
        delivery_handle_hashes: set[str],
    ) -> tuple[str, OutboxRecord]:
        matches = [
            (event_key, record)
            for event_key, record in self.outbox.items()
            if record.delivery_handle_hash in delivery_handle_hashes
        ]
        if len(matches) != 1:
            raise AnalyticsUnavailable("Unknown analytics delivery handle")
        return matches[0]

    def acquire_delivery(
        self,
        delivery_handle_hashes: set[str],
        *,
        now: datetime,
    ) -> tuple[str, OutboxRecord]:
        with self.lock:
            event_key, record = self.occurrence_for_handle_hashes(delivery_handle_hashes)
            if record.delivery_state in {"written", "failed", "discarded"}:
                return event_key, record
            if (
                record.delivery_state == "leased"
                and record.lease_expires_at is not None
                and record.lease_expires_at > now
            ):
                raise AnalyticsDeliveryRetry("Analytics delivery lease is active")
            record.delivery_state = "leased"
            record.lease_acquired_at = now
            record.lease_expires_at = now + DELIVERY_LEASE
            record.attempt_count += 1
            return event_key, record

    def persist_delivery_retry(
        self,
        event_key: str,
        *,
        lease_acquired_at: datetime,
        now: datetime,
    ) -> OutboxRecord:
        with self.lock:
            try:
                record = self.outbox[event_key]
            except KeyError as error:
                raise AnalyticsUnavailable("Unknown analytics occurrence") from error
            if record.delivery_state in {"written", "failed", "discarded"}:
                return record
            if record.lease_acquired_at != lease_acquired_at:
                raise AnalyticsDeliveryRetry("Analytics delivery lease changed")
            record.delivery_state = "queued"
            record.lease_acquired_at = None
            record.lease_expires_at = None
            if record.attempt_count >= 8:
                record.delivery_state = "failed"
                record.failure_code = "delivery_retry_exhausted"
                record.sealed_delivery_payload = None
                record.expires_at = now + TERMINAL_OUTBOX_TTL
            return record

    def persist_delivery_terminal(
        self,
        event_key: str,
        *,
        lease_acquired_at: datetime,
        state: Literal["written", "failed", "discarded"],
        now: datetime,
        failure_code: Literal["delivery_retry_exhausted", "sealed_payload_invalid"]
        | None = None,
    ) -> OutboxRecord | None:
        with self.lock:
            record = self.outbox.get(event_key)
            if record is None:
                if state == "discarded":
                    return None
                raise AnalyticsUnavailable("Unknown analytics occurrence")
            if record.delivery_state in {"written", "failed", "discarded"}:
                return record
            if record.lease_acquired_at != lease_acquired_at:
                raise AnalyticsDeliveryRetry("Analytics delivery lease changed")
            record.delivery_state = state
            record.lease_acquired_at = None
            record.lease_expires_at = None
            record.failure_code = failure_code
            record.sealed_delivery_payload = None
            record.expires_at = now + TERMINAL_OUTBOX_TTL
            return record

    def task_for_event(self, event_key: str) -> DeliveryTask:
        try:
            return self.tasks[self.outbox[event_key].task_name]
        except KeyError as error:
            raise AnalyticsUnavailable("Analytics task is unavailable") from error

    def task_for_name(self, task_name: str) -> DeliveryTask:
        try:
            return self.tasks[task_name]
        except KeyError as error:
            raise AnalyticsUnavailable("Unknown analytics task") from error

    def write_row(self, row: AnalyticsRow) -> None:
        existing = self.warehouse_rows.get(row.event_key)
        if existing is not None:
            if existing.payload_hash != row.payload_hash:
                raise AnalyticsConflict("event_id_conflict")
            return
        if self.fail_next_writes:
            self.fail_next_writes -= 1
            raise AnalyticsDeliveryRetry("Transient analytics warehouse failure")
        self.warehouse_rows[row.event_key] = row
        if self.raise_ambiguous_after_next_insert:
            self.raise_ambiguous_after_next_insert = False
            raise AnalyticsDeliveryRetry("Ambiguous analytics warehouse result")

    def is_subject_key_fenced(
        self,
        subject_key: str,
        *,
        version: str | None = None,
    ) -> bool:
        del version
        return subject_key in self._fenced_subject_keys

    def delete_subject_keys(
        self,
        subject_keys: set[str],
        fences: list[DeletionFenceRecord],
        *,
        counter_scope_hash: str | None = None,
    ) -> None:
        with self.lock:
            self._fenced_subject_keys.update(subject_keys)
            for fence in fences:
                self.deletion_fences[fence.fence_key] = fence

            event_keys = {
                event_key
                for event_key, record in self.outbox.items()
                if record.subject_key in subject_keys
            }
            task_names = {self.outbox[event_key].task_name for event_key in event_keys}
            for event_key in event_keys:
                self.outbox.pop(event_key, None)
                self.warehouse_rows.pop(event_key, None)
            for task_name in task_names:
                self.tasks.pop(task_name, None)
            for subject_key in subject_keys:
                self.linkable_counter_records.pop(subject_key, None)
            if counter_scope_hash is not None:
                self.linkable_counter_records.pop(counter_scope_hash, None)


class AnalyticsService:
    def __init__(
        self,
        *,
        project_id: str,
        environment: Literal["test", "development", "production"],
        keyring: AnalyticsKeyring,
        backend: Any,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        event_id_factory: Callable[[datetime], str] = uuid7,
        nonce_factory: Callable[[], str] = lambda: _urlsafe(secrets.token_bytes(24)),
        task_audience: str = "http://localhost/internal/v1/analytics/deliver",
        task_service_account: str = "local-task-delivery",
    ) -> None:
        self.project_id = project_id
        self.environment = environment
        self.keyring = keyring
        self.sealed_codec = SealedDeliveryCodec(keyring)
        self.backend = backend
        self.clock = clock
        self.event_id_factory = event_id_factory
        self.nonce_factory = nonce_factory
        self.task_audience = task_audience
        self.task_service_account = task_service_account

    def issue_profile_confirmed(self, *, subject_uid: str) -> IssuedAnalyticsEvent:
        return self._issue(
            subject_uid=subject_uid,
            event_name="profile_confirmed",
            properties=ProfileAnalyticsProperties(),
        )

    def issue_journey_draft_created(
        self,
        *,
        subject_uid: str,
        journey_schema_version: str,
        generator: JourneyGenerator,
        fallback_used: bool,
    ) -> IssuedAnalyticsEvent:
        return self._issue(
            subject_uid=subject_uid,
            event_name="journey_draft_created",
            properties=JourneyAnalyticsProperties(
                journeySchemaVersion=journey_schema_version,
                generator=generator,
                fallbackUsed=fallback_used,
            ),
        )

    def issue_journey_confirmed(
        self,
        *,
        subject_uid: str,
        journey_schema_version: str,
        generator: JourneyGenerator,
        fallback_used: bool,
    ) -> IssuedAnalyticsEvent:
        return self._issue(
            subject_uid=subject_uid,
            event_name="journey_confirmed",
            properties=JourneyAnalyticsProperties(
                journeySchemaVersion=journey_schema_version,
                generator=generator,
                fallbackUsed=fallback_used,
            ),
        )

    def issue_recommendation_presented(
        self,
        *,
        subject_uid: str,
        matching_contract_version: str,
        recommendation_type: RecommendationType,
        outcome: RecommendationOutcome,
        result_count: int,
    ) -> IssuedAnalyticsEvent:
        return self._issue(
            subject_uid=subject_uid,
            event_name="recommendation_presented",
            properties=RecommendationAnalyticsProperties(
                matchingContractVersion=matching_contract_version,
                recommendationType=recommendation_type,
                outcome=outcome,
                resultCount=result_count,
            ),
        )

    def _issue(
        self,
        *,
        subject_uid: str,
        event_name: EventName,
        properties: EventProperties,
    ) -> IssuedAnalyticsEvent:
        now = self.clock().astimezone(UTC)
        event_id = self.event_id_factory(now)
        self._validate_uuid7_timestamp(event_id, now)
        nonce = self.nonce_factory()
        version = self.keyring.current_version
        subject_key = self.keyring.subject_key(subject_uid, version=version)
        event_key = self.keyring.event_key(subject_key, event_id, version=version)
        property_payload = properties.model_dump(by_alias=True, mode="json")
        canonical_content = {
            "schemaVersion": ANALYTICS_SCHEMA_VERSION,
            "eventId": event_id,
            "eventName": event_name,
            "properties": property_payload,
            "eventTimestamp": now.isoformat(),
        }
        payload_hash = hashlib.sha256(_canonical_json(canonical_content)).hexdigest()
        row = self._build_row(
            event_id=event_id,
            event_name=event_name,
            properties=properties,
            now=now,
            subject_key=subject_key,
            subject_key_version=version,
            event_key=event_key,
            payload_hash=payload_hash,
        )
        receipt = self._mint_receipt(
            subject_uid=subject_uid,
            event_id=event_id,
            event_name=event_name,
            properties=properties,
            issued_at=now,
            nonce=nonce,
            key_version=version,
        )
        task = DeliveryTask(
            name=self.keyring.task_name(event_key, version=version),
            deliveryHandle=self.keyring.delivery_handle(
                event_key,
                nonce,
                version=version,
            ),
        )
        record = self._outbox_record(row, task)
        stored_row, _record, stored_task, _created = self.backend.register_occurrence(
            row,
            record,
            task,
        )
        try:
            self.backend.enqueue(stored_task)
        except AnalyticsEnqueueUnavailable:
            pass
        return IssuedAnalyticsEvent(
            eventId=stored_row.event_id,
            eventName=stored_row.event_name,
            properties=property_payload,
            actionReceipt=receipt,
            row=stored_row,
            task=stored_task,
        )

    def _outbox_record(self, row: AnalyticsRow, task: DeliveryTask) -> OutboxRecord:
        handle_hash = self.keyring.delivery_handle_hash(
            task.delivery_handle,
            version=row.subject_key_version,
        )
        return OutboxRecord(
            payloadHash=row.payload_hash,
            subjectKey=row.subject_key,
            subjectKeyVersion=row.subject_key_version,
            deliveryHandleHash=handle_hash,
            sealedDeliveryPayload=self.sealed_codec.seal(
                row,
                delivery_handle_hash=handle_hash,
            ),
            deliveryState="queued",
            taskName=task.name,
        )

    def _build_row(
        self,
        *,
        event_id: str,
        event_name: EventName,
        properties: EventProperties,
        now: datetime,
        subject_key: str,
        subject_key_version: str,
        event_key: str,
        payload_hash: str,
    ) -> AnalyticsRow:
        values: dict[str, Any] = {}
        if isinstance(properties, JourneyAnalyticsProperties):
            values.update(
                journey_schema_version=properties.journey_schema_version,
                journey_generator=properties.generator,
                journey_fallback_used=properties.fallback_used,
            )
        elif isinstance(properties, RecommendationAnalyticsProperties):
            values.update(
                matching_contract_version=properties.matching_contract_version,
                recommendation_type=properties.recommendation_type,
                recommendation_outcome=properties.outcome,
                result_count=properties.result_count,
            )
        return AnalyticsRow(
            event_date=now.astimezone(INDIA_TIMEZONE).date(),
            event_timestamp=now,
            event_name=event_name,
            event_id=event_id,
            event_key=event_key,
            payload_hash=payload_hash,
            subject_key=subject_key,
            subject_key_version=subject_key_version,
            environment=self.environment,
            **values,
        )

    def _mint_receipt(
        self,
        *,
        subject_uid: str,
        event_id: str,
        event_name: EventName,
        properties: EventProperties,
        issued_at: datetime,
        nonce: str,
        key_version: str,
    ) -> str:
        claims = ActionReceiptClaims(
            eventId=event_id,
            eventName=event_name,
            properties=properties,
            issuedAt=issued_at,
            expiresAt=issued_at + RECEIPT_LIFETIME,
            nonce=nonce,
            subjectBinding=self.keyring.subject_binding(
                subject_uid,
                event_id,
                nonce,
                version=key_version,
            ),
            keyVersion=key_version,
        )
        encoded = _urlsafe(_canonical_json(claims.model_dump(by_alias=True, mode="json")))
        signature = self.keyring.receipt_signature(encoded, version=key_version)
        return f"v1.{encoded}.{signature}"

    def verify_receipt(
        self,
        *,
        subject_uid: str,
        event_id: str,
        action_receipt: str,
    ) -> ActionReceiptClaims:
        try:
            receipt_version, encoded, signature = action_receipt.split(".")
            if receipt_version != "v1":
                raise ValueError("Unsupported receipt version")
            claims = ActionReceiptClaims.model_validate_json(_decode_urlsafe(encoded))
        except Exception as error:
            raise AnalyticsReceiptError("Invalid analytics receipt") from error
        expected_signature = self.keyring.receipt_signature(
            encoded,
            version=claims.key_version,
        )
        if not hmac.compare_digest(signature, expected_signature):
            raise AnalyticsReceiptError("Invalid analytics receipt signature")
        if claims.event_id != event_id:
            raise AnalyticsConflict("event_id_conflict")
        expected_binding = self.keyring.subject_binding(
            subject_uid,
            claims.event_id,
            claims.nonce,
            version=claims.key_version,
        )
        if not hmac.compare_digest(claims.subject_binding, expected_binding):
            raise AnalyticsReceiptError("Analytics receipt subject binding is invalid")
        now = self.clock().astimezone(UTC)
        if now > claims.expires_at.astimezone(UTC):
            raise AnalyticsReceiptError("Analytics receipt has expired")
        if claims.issued_at.astimezone(UTC) > now + timedelta(minutes=1):
            raise AnalyticsReceiptError("Analytics receipt was issued in the future")
        self._validate_uuid7_timestamp(claims.event_id, claims.issued_at)
        return claims

    @staticmethod
    def _validate_uuid7_timestamp(event_id: str, timestamp: datetime) -> None:
        try:
            parsed = UUID(event_id)
        except ValueError as error:
            raise AnalyticsReceiptError("Invalid analytics event ID") from error
        embedded = parsed.int >> 80
        expected = int(timestamp.timestamp() * 1000)
        if parsed.version != 7 or abs(embedded - expected) > 60_000:
            raise AnalyticsReceiptError("Analytics event ID timestamp is invalid")

    def _row_from_claims(self, subject_uid: str, claims: ActionReceiptClaims) -> AnalyticsRow:
        subject_key = self.keyring.subject_key(
            subject_uid,
            version=claims.key_version,
        )
        event_key = self.keyring.event_key(
            subject_key,
            claims.event_id,
            version=claims.key_version,
        )
        canonical_content = {
            "schemaVersion": claims.schema_version,
            "eventId": claims.event_id,
            "eventName": claims.event_name,
            "properties": claims.properties.model_dump(by_alias=True, mode="json"),
            "eventTimestamp": claims.issued_at.astimezone(UTC).isoformat(),
        }
        return self._build_row(
            event_id=claims.event_id,
            event_name=claims.event_name,
            properties=claims.properties,
            now=claims.issued_at.astimezone(UTC),
            subject_key=subject_key,
            subject_key_version=claims.key_version,
            event_key=event_key,
            payload_hash=hashlib.sha256(_canonical_json(canonical_content)).hexdigest(),
        )

    def resume(
        self,
        *,
        subject_uid: str,
        request: AnalyticsReceiptRequest,
    ) -> AnalyticsStatusResponse:
        claims = self.verify_receipt(
            subject_uid=subject_uid,
            event_id=request.event_id,
            action_receipt=request.action_receipt,
        )
        row = self._row_from_claims(subject_uid, claims)
        if self.backend.is_subject_key_fenced(
            row.subject_key,
            version=row.subject_key_version,
        ):
            return AnalyticsStatusResponse(
                eventId=row.event_id,
                status="discarded",
                duplicate=True,
            )
        task = DeliveryTask(
            name=self.keyring.task_name(
                row.event_key,
                version=claims.key_version,
            ),
            deliveryHandle=self.keyring.delivery_handle(
                row.event_key,
                claims.nonce,
                version=claims.key_version,
            ),
        )
        record = self._outbox_record(row, task)
        _stored_row, stored_record, stored_task, created = self.backend.register_occurrence(
            row,
            record,
            task,
        )
        if stored_record.delivery_state == "written":
            return AnalyticsStatusResponse(
                eventId=row.event_id,
                status="written",
                duplicate=True,
            )
        if stored_record.delivery_state in {"failed", "discarded"}:
            return AnalyticsStatusResponse(
                eventId=row.event_id,
                status=stored_record.delivery_state,
                duplicate=not created,
            )
        try:
            self.backend.enqueue(stored_task)
        except AnalyticsEnqueueUnavailable:
            pass
        return AnalyticsStatusResponse(
            eventId=row.event_id,
            status="queued",
            duplicate=False,
        )

    def _validate_task_claims(self, claims: TaskAuthClaims) -> None:
        if (
            claims.issuer not in {"https://accounts.google.com", "accounts.google.com"}
            or claims.audience != self.task_audience
            or claims.service_account != self.task_service_account
        ):
            raise TaskAuthorizationError("Task OIDC claims are not authorized")

    def deliver(
        self,
        delivery_handle: str,
        *,
        claims: TaskAuthClaims,
        before_warehouse_write: Callable[[], None] | None = None,
    ) -> DeliveryResult:
        self._validate_task_claims(claims)
        with self.backend.lock:
            handle_hashes = {
                self.keyring.delivery_handle_hash(delivery_handle, version=version)
                for version in self.keyring.keys
            }
            now = self.clock().astimezone(UTC)
            event_key, record = self.backend.acquire_delivery(
                handle_hashes,
                now=now,
            )
            if record.delivery_state == "written":
                return DeliveryResult(status="written")
            if record.delivery_state in {"failed", "discarded"}:
                return DeliveryResult(status=record.delivery_state)
            if record.lease_acquired_at is None:
                raise AnalyticsDeliveryRetry("Analytics delivery lease is unavailable")
            lease_acquired_at = record.lease_acquired_at
            if self.backend.is_subject_key_fenced(
                record.subject_key,
                version=record.subject_key_version,
            ):
                self.backend.persist_delivery_terminal(
                    event_key,
                    lease_acquired_at=lease_acquired_at,
                    state="discarded",
                    now=now,
                )
                return DeliveryResult(status="discarded")

            try:
                if record.sealed_delivery_payload is None:
                    raise SealedPayloadError("sealed_payload_invalid")
                row = self.sealed_codec.open(
                    record.sealed_delivery_payload,
                    event_key=event_key,
                    payload_hash=record.payload_hash,
                    delivery_handle_hash=record.delivery_handle_hash,
                )
            except SealedPayloadError:
                self.backend.persist_delivery_terminal(
                    event_key,
                    lease_acquired_at=lease_acquired_at,
                    state="failed",
                    failure_code="sealed_payload_invalid",
                    now=now,
                )
                return DeliveryResult(status="failed")

            if before_warehouse_write is not None:
                before_warehouse_write()
            if self.backend.is_subject_key_fenced(
                row.subject_key,
                version=row.subject_key_version,
            ):
                self.backend.persist_delivery_terminal(
                    event_key,
                    lease_acquired_at=lease_acquired_at,
                    state="discarded",
                    now=now,
                )
                return DeliveryResult(status="discarded")
            try:
                self.backend.write_row(row)
            except AnalyticsDeliveryRetry:
                persisted = self.backend.persist_delivery_retry(
                    event_key,
                    lease_acquired_at=lease_acquired_at,
                    now=now,
                )
                if persisted.delivery_state == "failed":
                    return DeliveryResult(status="failed")
                if persisted.delivery_state in {"written", "discarded"}:
                    return DeliveryResult(status=persisted.delivery_state)
                raise
            self.backend.persist_delivery_terminal(
                event_key,
                lease_acquired_at=lease_acquired_at,
                state="written",
                now=now,
            )
            return DeliveryResult(status="written")

    def run_task(self, task_name: str, *, claims: TaskAuthClaims) -> DeliveryResult:
        task = self.backend.task_for_name(task_name)
        return self.deliver(task.delivery_handle, claims=claims)

    def delete_subject(self, subject_uid: str) -> None:
        now = self.clock().astimezone(UTC)
        subject_keys = self.keyring.subject_keys_for_deletion(subject_uid)
        fences = [
            DeletionFenceRecord(
                fenceKey=self.keyring.deletion_fence_key(
                    subject_uid,
                    version=version,
                ),
                expiresAt=now + DELETION_FENCE_TTL,
            )
            for version in subject_keys
        ]
        self.backend.delete_subject_keys(
            set(subject_keys.values()),
            fences,
            counter_scope_hash=hashlib.sha256(subject_uid.encode()).hexdigest(),
        )
