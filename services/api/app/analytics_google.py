from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .analytics import (
    DELIVERY_LEASE,
    TERMINAL_OUTBOX_TTL,
    AnalyticsConflict,
    AnalyticsDeliveryRetry,
    AnalyticsEnqueueUnavailable,
    AnalyticsKeyring,
    AnalyticsRow,
    AnalyticsService,
    AnalyticsUnavailable,
    DeletionFenceRecord,
    DeliveryTask,
    OutboxRecord,
    TaskAuthClaims,
    TaskAuthorizationError,
    TaskTokenVerifier,
)

MAXIMUM_BYTES_BILLED = 20 * 1024 * 1024
OUTBOX_COLLECTION = "analytics_outbox_v1"
DELETION_FENCE_COLLECTION = "analytics_deletion_fences_v1"
QUOTA_COUNTER_COLLECTION = "runtime_quota_counters_v1"

BIGQUERY_PARAMETER_TYPES = {
    "event_date": "DATE",
    "event_timestamp": "TIMESTAMP",
    "schema_version": "STRING",
    "event_name": "STRING",
    "event_id": "STRING",
    "event_key": "STRING",
    "payload_hash": "STRING",
    "subject_key": "STRING",
    "subject_key_version": "STRING",
    "environment": "STRING",
    "journey_schema_version": "STRING",
    "journey_generator": "STRING",
    "journey_fallback_used": "BOOL",
    "matching_contract_version": "STRING",
    "recommendation_type": "STRING",
    "recommendation_outcome": "STRING",
    "result_count": "INT64",
}


class ProductionAnalyticsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    project_id: str = Field(
        alias="projectId",
        min_length=4,
        pattern=r"^[a-z][a-z0-9-]{2,28}[a-z0-9]$",
    )
    firestore_database_id: Literal["(default)"] = Field(alias="firestoreDatabaseId")
    location: Literal["asia-south1"]
    private_dataset_id: Literal["sakhi_analytics"] = Field(alias="privateDatasetId")
    analytics_table_id: Literal["checkpoint_events_v1"] = Field(alias="analyticsTableId")
    reporting_dataset_id: Literal["sakhi_reporting"] = Field(alias="reportingDatasetId")
    reporting_view_id: Literal["checkpoint_metrics_v1"] = Field(alias="reportingViewId")
    queue_id: Literal["analytics-delivery"] = Field(alias="queueId")
    task_service_account: str = Field(
        alias="taskServiceAccount",
        pattern=r"^sakhi-task-delivery@[^@]+\.iam\.gserviceaccount\.com$",
    )
    task_audience: str = Field(alias="taskAudience", pattern=r"^https://")
    hmac_secret_name: Literal["sakhi-analytics-hmac-key"] = Field(alias="hmacSecretName")
    hmac_secret_versions: list[str] = Field(
        alias="hmacSecretVersions",
        min_length=1,
    )
    current_hmac_secret_version: str = Field(alias="currentHmacSecretVersion")

    @model_validator(mode="after")
    def current_hmac_version_is_resolvable(self) -> ProductionAnalyticsConfig:
        if self.current_hmac_secret_version not in self.hmac_secret_versions:
            raise ValueError("Current HMAC secret version must be in hmacSecretVersions")
        if len(set(self.hmac_secret_versions)) != len(self.hmac_secret_versions):
            raise ValueError("HMAC secret versions must be unique")
        return self


def production_config_from_settings(settings: Any) -> ProductionAnalyticsConfig:
    return ProductionAnalyticsConfig(
        projectId=settings.firebase_project_id,
        firestoreDatabaseId=settings.firestore_database_id,
        location=settings.analytics_location,
        privateDatasetId=settings.analytics_private_dataset_id,
        analyticsTableId=settings.analytics_table_id,
        reportingDatasetId=settings.analytics_reporting_dataset_id,
        reportingViewId=settings.analytics_reporting_view_id,
        queueId=settings.analytics_queue_id,
        taskServiceAccount=settings.analytics_task_service_account,
        taskAudience=settings.analytics_task_audience,
        hmacSecretName=settings.analytics_hmac_secret_name,
        hmacSecretVersions=settings.analytics_hmac_secret_versions,
        currentHmacSecretVersion=settings.analytics_current_hmac_secret_version,
    )


class SecretManagerAnalyticsKeyLoader:
    def __init__(self, *, client: Any, config: ProductionAnalyticsConfig) -> None:
        self.client = client
        self.config = config

    def load(self) -> AnalyticsKeyring:
        try:
            keys = {
                version: self.client.access_secret_version(
                    request={
                        "name": (
                            f"projects/{self.config.project_id}/secrets/"
                            f"{self.config.hmac_secret_name}/versions/{version}"
                        )
                    }
                ).payload.data
                for version in self.config.hmac_secret_versions
            }
            return AnalyticsKeyring(
                project_id=self.config.project_id,
                keys=keys,
                current_version=self.config.current_hmac_secret_version,
            )
        except Exception as error:
            raise AnalyticsUnavailable("analytics_configuration_required") from error


class GoogleBigQueryQueryRunner:
    def __init__(
        self,
        *,
        client: Any,
        scalar_parameter_factory: Callable[[str, str, object], object],
        array_parameter_factory: Callable[[str, str, list[str]], object],
        job_config_factory: Callable[..., object],
    ) -> None:
        self.client = client
        self.scalar_parameter_factory = scalar_parameter_factory
        self.array_parameter_factory = array_parameter_factory
        self.job_config_factory = job_config_factory

    def __call__(
        self,
        *,
        query: str,
        parameters: Mapping[str, object],
        maximum_bytes_billed: int,
        location: str,
    ) -> object:
        query_parameters: list[object] = []
        for name, value in parameters.items():
            if name == "subject_keys":
                if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                    raise AnalyticsUnavailable("analytics_configuration_required")
                query_parameters.append(self.array_parameter_factory(name, "STRING", value))
                continue
            try:
                parameter_type = BIGQUERY_PARAMETER_TYPES[name]
            except KeyError as error:
                raise AnalyticsUnavailable("analytics_configuration_required") from error
            query_parameters.append(self.scalar_parameter_factory(name, parameter_type, value))
        job_config = self.job_config_factory(
            query_parameters=query_parameters,
            maximum_bytes_billed=maximum_bytes_billed,
            use_legacy_sql=False,
        )
        job = self.client.query(
            query,
            job_config=job_config,
            location=location,
        )
        return job.result()


class GoogleFirestoreAnalyticsGateway:
    def __init__(
        self,
        *,
        client: Any,
        transactional: Callable[[Callable[..., object]], Callable[..., object]],
        field_filter_factory: Callable[[str, str, object], object],
    ) -> None:
        self.client = client
        self.transactional = transactional
        self.field_filter_factory = field_filter_factory

    def create_occurrence(
        self,
        *,
        collection: str,
        document_id: str,
        document: dict[str, object],
    ) -> tuple[str, dict[str, object]]:
        stored_id, stored_document, _created = self.create_occurrence_with_status(
            collection=collection,
            document_id=document_id,
            document=document,
        )
        return stored_id, stored_document

    def create_occurrence_with_status(
        self,
        *,
        collection: str,
        document_id: str,
        document: dict[str, object],
    ) -> tuple[str, dict[str, object], bool]:
        reference = self.client.collection(collection).document(document_id)
        transaction = self.client.transaction()

        @self.transactional
        def create_in_transaction(active_transaction: Any):
            snapshot = reference.get(transaction=active_transaction)
            if snapshot.exists:
                existing = snapshot.to_dict() or {}
                if existing.get("payloadHash") != document.get("payloadHash"):
                    raise AnalyticsConflict("event_id_conflict")
                return document_id, existing, False
            active_transaction.create(reference, document)
            return document_id, document, True

        return create_in_transaction(transaction)

    def find_by_delivery_handle_hashes(
        self,
        *,
        collection: str,
        hashes: list[str],
        limit: int,
    ) -> list[tuple[str, dict[str, object]]]:
        if not hashes:
            return []
        query = (
            self.client.collection(collection)
            .where(
                filter=self.field_filter_factory(
                    "deliveryHandleHash",
                    "in",
                    hashes,
                )
            )
            .limit(limit)
        )
        return [(snapshot.id, snapshot.to_dict() or {}) for snapshot in query.stream()]

    def query_documents(
        self,
        *,
        collection: str,
        filters: list[tuple[str, str, object]],
        limit: int | None = None,
    ) -> list[tuple[str, dict[str, object]]]:
        query = self.client.collection(collection)
        for field, operator, value in filters:
            query = query.where(
                filter=self.field_filter_factory(field, operator, value)
            )
        if limit is not None:
            query = query.limit(limit)
        return [(snapshot.id, snapshot.to_dict() or {}) for snapshot in query.stream()]

    def get_document(
        self,
        *,
        collection: str,
        document_id: str,
    ) -> dict[str, object] | None:
        snapshot = self.client.collection(collection).document(document_id).get()
        if not snapshot.exists:
            return None
        return snapshot.to_dict() or {}

    def acquire_delivery_lease(
        self,
        *,
        collection: str,
        document_id: str,
        delivery_handle_hashes: set[str],
        now: datetime,
    ) -> dict[str, object]:
        reference = self.client.collection(collection).document(document_id)
        transaction = self.client.transaction()

        @self.transactional
        def acquire_in_transaction(active_transaction: Any) -> dict[str, object]:
            snapshot = reference.get(transaction=active_transaction)
            if not snapshot.exists:
                raise AnalyticsUnavailable("Unknown analytics delivery handle")
            document = snapshot.to_dict() or {}
            if document.get("deliveryHandleHash") not in delivery_handle_hashes:
                raise AnalyticsUnavailable("Unknown analytics delivery handle")
            state = document.get("deliveryState")
            if state in {"written", "failed", "discarded"}:
                return document
            lease_expires_at = _utc_datetime(document.get("leaseExpiresAt"))
            if state == "leased" and lease_expires_at is not None and lease_expires_at > now:
                raise AnalyticsDeliveryRetry("Analytics delivery lease is active")
            attempt_count = document.get("attemptCount")
            if not isinstance(attempt_count, int) or isinstance(attempt_count, bool):
                raise AnalyticsUnavailable("analytics_configuration_required")
            updates: dict[str, object] = {
                "deliveryState": "leased",
                "leaseAcquiredAt": now,
                "leaseExpiresAt": now + DELIVERY_LEASE,
                "attemptCount": attempt_count + 1,
            }
            active_transaction.update(reference, updates)
            return {**document, **updates}

        return acquire_in_transaction(transaction)

    def persist_delivery_retry(
        self,
        *,
        collection: str,
        document_id: str,
        lease_acquired_at: datetime,
        now: datetime,
    ) -> dict[str, object]:
        return self._persist_delivery_transition(
            collection=collection,
            document_id=document_id,
            lease_acquired_at=lease_acquired_at,
            now=now,
            state="queued",
        )

    def persist_delivery_terminal(
        self,
        *,
        collection: str,
        document_id: str,
        lease_acquired_at: datetime,
        state: Literal["written", "failed", "discarded"],
        now: datetime,
        failure_code: str | None,
    ) -> dict[str, object] | None:
        return self._persist_delivery_transition(
            collection=collection,
            document_id=document_id,
            lease_acquired_at=lease_acquired_at,
            now=now,
            state=state,
            failure_code=failure_code,
            allow_missing=state == "discarded",
        )

    def _persist_delivery_transition(
        self,
        *,
        collection: str,
        document_id: str,
        lease_acquired_at: datetime,
        now: datetime,
        state: Literal["queued", "written", "failed", "discarded"],
        failure_code: str | None = None,
        allow_missing: bool = False,
    ) -> dict[str, object] | None:
        reference = self.client.collection(collection).document(document_id)
        transaction = self.client.transaction()

        @self.transactional
        def persist_in_transaction(
            active_transaction: Any,
        ) -> dict[str, object] | None:
            snapshot = reference.get(transaction=active_transaction)
            if not snapshot.exists:
                if allow_missing:
                    return None
                raise AnalyticsUnavailable("Unknown analytics occurrence")
            document = snapshot.to_dict() or {}
            current_state = document.get("deliveryState")
            if current_state in {"written", "failed", "discarded"}:
                return document
            if _utc_datetime(document.get("leaseAcquiredAt")) != lease_acquired_at:
                raise AnalyticsDeliveryRetry("Analytics delivery lease changed")
            updates: dict[str, object] = {
                "deliveryState": state,
                "leaseAcquiredAt": None,
                "leaseExpiresAt": None,
            }
            attempt_count = document.get("attemptCount")
            if state == "queued" and attempt_count == 8:
                updates.update(
                    deliveryState="failed",
                    failureCode="delivery_retry_exhausted",
                    sealedDeliveryPayload=None,
                    expiresAt=now + TERMINAL_OUTBOX_TTL,
                )
            elif state != "queued":
                updates.update(
                    failureCode=failure_code,
                    sealedDeliveryPayload=None,
                    expiresAt=now + TERMINAL_OUTBOX_TTL,
                )
            active_transaction.update(reference, updates)
            return {**document, **updates}

        return persist_in_transaction(transaction)

    def set_documents(
        self,
        *,
        collection: str,
        documents: Mapping[str, dict[str, object]],
    ) -> None:
        for document_id, document in documents.items():
            self.client.collection(collection).document(document_id).set(
                document,
                merge=True,
            )

    def delete_documents(
        self,
        *,
        documents: list[tuple[str, str]],
        updates: list[tuple[str, str, dict[str, object]]],
    ) -> None:
        batch = self.client.batch()
        for collection, document_id in documents:
            batch.delete(self.client.collection(collection).document(document_id))
        for collection, document_id, document in updates:
            batch.set(
                self.client.collection(collection).document(document_id),
                document,
                merge=True,
            )
        batch.commit()


def _utc_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return None
        return value.astimezone(UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is not None:
            return parsed.astimezone(UTC)
    return None


class CloudTasksAnalyticsQueue:
    def __init__(
        self,
        *,
        client: Any,
        config: ProductionAnalyticsConfig,
        already_exists_errors: tuple[type[BaseException], ...] = (),
        not_found_errors: tuple[type[BaseException], ...] = (),
    ) -> None:
        self.client = client
        self.config = config
        self.already_exists_errors = already_exists_errors
        self.not_found_errors = not_found_errors

    @property
    def parent(self) -> str:
        return (
            f"projects/{self.config.project_id}/locations/{self.config.location}/"
            f"queues/{self.config.queue_id}"
        )

    def enqueue(self, delivery_task: DeliveryTask) -> None:
        request: dict[str, object] = {
            "parent": self.parent,
            "task": {
                "name": f"{self.parent}/tasks/{delivery_task.name}",
                "http_request": {
                    "url": self.config.task_audience,
                    "http_method": "POST",
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps(
                        delivery_task.body,
                        separators=(",", ":"),
                        sort_keys=True,
                    ).encode(),
                    "oidc_token": {
                        "service_account_email": self.config.task_service_account,
                        "audience": self.config.task_audience,
                    },
                },
            },
        }
        try:
            self.client.create_task(request=request)
        except Exception as error:
            if self.already_exists_errors and isinstance(error, self.already_exists_errors):
                return
            raise AnalyticsEnqueueUnavailable("Analytics queue unavailable") from error

    def cancel(self, task_name: str) -> None:
        full_name = f"{self.parent}/tasks/{task_name}"
        try:
            self.client.delete_task(request={"name": full_name})
        except Exception as error:
            if self.not_found_errors and isinstance(error, self.not_found_errors):
                return
            raise AnalyticsDeliveryRetry("Transient analytics task cancellation failure") from error


class GoogleTaskTokenVerifier:
    def __init__(
        self,
        *,
        verify_google_token: Callable[..., Mapping[str, object]],
        audience: str,
        service_account: str,
    ) -> None:
        self.verify_google_token = verify_google_token
        self.audience = audience
        self.service_account = service_account

    def verify(self, token: str) -> TaskAuthClaims:
        try:
            claims = self.verify_google_token(token, audience=self.audience)
            issuer = claims.get("iss")
            audience = claims.get("aud")
            service_account = claims.get("email")
            if (
                issuer not in {"https://accounts.google.com", "accounts.google.com"}
                or audience != self.audience
                or service_account != self.service_account
                or claims.get("email_verified") is not True
            ):
                raise ValueError("Unauthorized task token")
            return TaskAuthClaims(
                issuer=str(issuer),
                audience=str(audience),
                serviceAccount=str(service_account),
            )
        except Exception as error:
            raise TaskAuthorizationError("Task authentication required") from error


class FirestoreAnalyticsOutboxStore:
    def __init__(
        self,
        *,
        gateway: Any,
        keyring: AnalyticsKeyring,
        collection: str = OUTBOX_COLLECTION,
    ) -> None:
        self.gateway = gateway
        self.keyring = keyring
        self.collection = collection

    def create_occurrence(
        self,
        *,
        event_key: str,
        record: OutboxRecord,
    ) -> tuple[str, dict[str, object]]:
        document = record.model_dump(
            by_alias=True,
            exclude_none=False,
            mode="json",
        )
        try:
            return self.gateway.create_occurrence(
                collection=self.collection,
                document_id=event_key,
                document=document,
            )
        except AnalyticsConflict:
            raise
        except Exception as error:
            raise AnalyticsUnavailable("analytics_configuration_required") from error

    def register_occurrence(
        self,
        *,
        event_key: str,
        record: OutboxRecord,
    ) -> tuple[OutboxRecord, bool]:
        document = record.model_dump(
            by_alias=True,
            exclude_none=False,
            mode="json",
        )
        try:
            _stored_id, stored_document, created = self.gateway.create_occurrence_with_status(
                collection=self.collection,
                document_id=event_key,
                document=document,
            )
            return OutboxRecord.model_validate(stored_document), created
        except AnalyticsConflict:
            raise
        except Exception as error:
            raise AnalyticsUnavailable("analytics_configuration_required") from error

    def occurrence_for_handle(self, delivery_handle: str) -> tuple[str, OutboxRecord]:
        hashes = [
            self.keyring.delivery_handle_hash(delivery_handle, version=version)
            for version in self.keyring.keys
        ]
        try:
            matches = self.gateway.find_by_delivery_handle_hashes(
                collection=self.collection,
                hashes=hashes,
                limit=2,
            )
            if len(matches) != 1:
                raise AnalyticsUnavailable("Unknown analytics delivery handle")
            event_key, document = matches[0]
            return event_key, OutboxRecord.model_validate(document)
        except AnalyticsUnavailable:
            raise
        except Exception as error:
            raise AnalyticsUnavailable("Unknown analytics delivery handle") from error

    def acquire_delivery(
        self,
        delivery_handle_hashes: set[str],
        *,
        now: datetime,
    ) -> tuple[str, OutboxRecord]:
        try:
            matches = self.gateway.find_by_delivery_handle_hashes(
                collection=self.collection,
                hashes=sorted(delivery_handle_hashes),
                limit=2,
            )
            if len(matches) != 1:
                raise AnalyticsUnavailable("Unknown analytics delivery handle")
            event_key, _document = matches[0]
            leased_document = self.gateway.acquire_delivery_lease(
                collection=self.collection,
                document_id=event_key,
                delivery_handle_hashes=delivery_handle_hashes,
                now=now,
            )
            return event_key, OutboxRecord.model_validate(leased_document)
        except (AnalyticsDeliveryRetry, AnalyticsUnavailable):
            raise
        except Exception as error:
            raise AnalyticsUnavailable("analytics_configuration_required") from error

    def persist_delivery_retry(
        self,
        event_key: str,
        *,
        lease_acquired_at: datetime,
        now: datetime,
    ) -> OutboxRecord:
        try:
            document = self.gateway.persist_delivery_retry(
                collection=self.collection,
                document_id=event_key,
                lease_acquired_at=lease_acquired_at,
                now=now,
            )
            return OutboxRecord.model_validate(document)
        except (AnalyticsDeliveryRetry, AnalyticsUnavailable):
            raise
        except Exception as error:
            raise AnalyticsUnavailable("analytics_configuration_required") from error

    def persist_delivery_terminal(
        self,
        event_key: str,
        *,
        lease_acquired_at: datetime,
        state: Literal["written", "failed", "discarded"],
        now: datetime,
        failure_code: str | None,
    ) -> OutboxRecord | None:
        try:
            document = self.gateway.persist_delivery_terminal(
                collection=self.collection,
                document_id=event_key,
                lease_acquired_at=lease_acquired_at,
                state=state,
                now=now,
                failure_code=failure_code,
            )
            return None if document is None else OutboxRecord.model_validate(document)
        except (AnalyticsDeliveryRetry, AnalyticsUnavailable):
            raise
        except Exception as error:
            raise AnalyticsUnavailable("analytics_configuration_required") from error

    def is_subject_key_fenced(self, subject_key: str, *, version: str) -> bool:
        fence_key = self.keyring.deletion_fence_key_for_subject_key(
            subject_key,
            version=version,
        )
        try:
            return (
                self.gateway.get_document(
                    collection=DELETION_FENCE_COLLECTION,
                    document_id=fence_key,
                )
                is not None
            )
        except Exception as error:
            raise AnalyticsUnavailable("analytics_configuration_required") from error

    def begin_subject_deletion(
        self,
        subject_keys: set[str],
        fences: list[DeletionFenceRecord],
    ) -> list[str]:
        try:
            self.gateway.set_documents(
                collection=DELETION_FENCE_COLLECTION,
                documents={
                    fence.fence_key: {
                        "expiresAt": fence.expires_at,
                        "deletionState": "pending",
                    }
                    for fence in fences
                },
            )
            occurrences = self.gateway.query_documents(
                collection=self.collection,
                filters=[("subjectKey", "in", sorted(subject_keys))],
            )
            return sorted(
                {
                    task_name
                    for _event_key, document in occurrences
                    if isinstance((task_name := document.get("taskName")), str)
                }
            )
        except Exception as error:
            raise AnalyticsUnavailable("analytics_configuration_required") from error

    def mark_deletion_retry(self, fences: list[DeletionFenceRecord]) -> None:
        try:
            self.gateway.set_documents(
                collection=DELETION_FENCE_COLLECTION,
                documents={
                    fence.fence_key: {
                        "expiresAt": fence.expires_at,
                        "deletionState": "retry_pending",
                    }
                    for fence in fences
                },
            )
        except Exception as error:
            raise AnalyticsUnavailable("analytics_configuration_required") from error

    def finish_subject_deletion(
        self,
        subject_keys: set[str],
        fences: list[DeletionFenceRecord],
        *,
        counter_scope_hash: str | None,
    ) -> None:
        try:
            occurrences = self.gateway.query_documents(
                collection=self.collection,
                filters=[("subjectKey", "in", sorted(subject_keys))],
            )
            counters: list[tuple[str, dict[str, object]]] = []
            if counter_scope_hash is not None:
                counters = self.gateway.query_documents(
                    collection=QUOTA_COUNTER_COLLECTION,
                    filters=[
                        ("scopeKind", "==", "subject"),
                        ("scopeHash", "==", counter_scope_hash),
                    ],
                )
            self.gateway.delete_documents(
                documents=[
                    *[(self.collection, event_key) for event_key, _document in occurrences],
                    *[
                        (QUOTA_COUNTER_COLLECTION, document_id)
                        for document_id, _document in counters
                    ],
                ],
                updates=[
                    (
                        DELETION_FENCE_COLLECTION,
                        fence.fence_key,
                        {
                            "expiresAt": fence.expires_at,
                            "deletionState": "complete",
                        },
                    )
                    for fence in fences
                ],
            )
        except Exception as error:
            raise AnalyticsUnavailable("analytics_configuration_required") from error


class BigQueryAnalyticsWarehouse:
    def __init__(
        self,
        *,
        query_runner: Callable[..., object],
        config: ProductionAnalyticsConfig,
    ) -> None:
        self.query_runner = query_runner
        self.config = config

    @property
    def table(self) -> str:
        return (
            f"{self.config.project_id}.{self.config.private_dataset_id}."
            f"{self.config.analytics_table_id}"
        )

    def write_row(self, row: AnalyticsRow) -> None:
        columns = tuple(type(row).model_fields)
        source = ",\n  ".join(f"@{column} AS {column}" for column in columns)
        insert_columns = ", ".join(columns)
        insert_values = ", ".join(f"source.{column}" for column in columns)
        query = f"""\
ASSERT NOT EXISTS (
  SELECT 1 FROM `{self.table}`
  WHERE event_date = @event_date
    AND event_date >= DATE_SUB(CURRENT_DATE("Asia/Kolkata"), INTERVAL 90 DAY)
    AND event_key = @event_key
    AND payload_hash != @payload_hash
) AS "event_id_conflict";
MERGE `{self.table}` AS target
USING (
  SELECT
    {source}
  FROM (SELECT 1)
  WHERE NOT EXISTS (
    SELECT 1 FROM `{self.table}`
    WHERE event_date = @event_date
      AND event_date >= DATE_SUB(CURRENT_DATE("Asia/Kolkata"), INTERVAL 90 DAY)
      AND event_key = @event_key
  )
) AS source
ON FALSE
WHEN NOT MATCHED THEN
  INSERT ({insert_columns})
  VALUES ({insert_values})
"""
        try:
            self.query_runner(
                query=query,
                parameters=row.model_dump(mode="json"),
                maximum_bytes_billed=MAXIMUM_BYTES_BILLED,
                location=self.config.location,
            )
        except Exception as error:
            if "event_id_conflict" in str(error):
                raise AnalyticsConflict("event_id_conflict") from error
            raise AnalyticsDeliveryRetry("Transient analytics warehouse failure") from error

    def delete_subject_keys(self, subject_keys: set[str]) -> None:
        if not subject_keys:
            return
        query = f"""\
DELETE FROM `{self.table}`
WHERE event_date >= DATE_SUB(CURRENT_DATE("Asia/Kolkata"), INTERVAL 90 DAY)
  AND subject_key IN UNNEST(@subject_keys)
"""
        try:
            self.query_runner(
                query=query,
                parameters={"subject_keys": sorted(subject_keys)},
                maximum_bytes_billed=MAXIMUM_BYTES_BILLED,
                location=self.config.location,
            )
        except Exception as error:
            raise AnalyticsDeliveryRetry("Transient analytics deletion failure") from error


class GoogleAnalyticsBackend:
    """Firestore-authoritative delivery state with bounded BigQuery coordination."""

    def __init__(
        self,
        *,
        outbox: FirestoreAnalyticsOutboxStore,
        queue: CloudTasksAnalyticsQueue,
        warehouse: BigQueryAnalyticsWarehouse,
    ) -> None:
        self.outbox_store = outbox
        self.queue = queue
        self.warehouse = warehouse
        self.lock = RLock()

    def register_occurrence(
        self,
        row: AnalyticsRow,
        record: OutboxRecord,
        task: DeliveryTask,
    ) -> tuple[AnalyticsRow, OutboxRecord, DeliveryTask, bool]:
        stored_record, created = self.outbox_store.register_occurrence(
            event_key=row.event_key,
            record=record,
        )
        return row, stored_record, task, created

    def enqueue(self, task: DeliveryTask) -> None:
        self.queue.enqueue(task)

    def occurrence_for_handle_hashes(
        self,
        delivery_handle_hashes: set[str],
    ) -> tuple[str, OutboxRecord]:
        try:
            matches = self.outbox_store.gateway.find_by_delivery_handle_hashes(
                collection=self.outbox_store.collection,
                hashes=sorted(delivery_handle_hashes),
                limit=2,
            )
            if len(matches) != 1:
                raise AnalyticsUnavailable("Unknown analytics delivery handle")
            event_key, document = matches[0]
            return event_key, OutboxRecord.model_validate(document)
        except AnalyticsUnavailable:
            raise
        except Exception as error:
            raise AnalyticsUnavailable("analytics_configuration_required") from error

    def acquire_delivery(
        self,
        delivery_handle_hashes: set[str],
        *,
        now: datetime,
    ) -> tuple[str, OutboxRecord]:
        return self.outbox_store.acquire_delivery(delivery_handle_hashes, now=now)

    def persist_delivery_retry(
        self,
        event_key: str,
        *,
        lease_acquired_at: datetime,
        now: datetime,
    ) -> OutboxRecord:
        return self.outbox_store.persist_delivery_retry(
            event_key,
            lease_acquired_at=lease_acquired_at,
            now=now,
        )

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
        return self.outbox_store.persist_delivery_terminal(
            event_key,
            lease_acquired_at=lease_acquired_at,
            state=state,
            now=now,
            failure_code=failure_code,
        )

    def write_row(self, row: AnalyticsRow) -> None:
        self.warehouse.write_row(row)

    def is_subject_key_fenced(
        self,
        subject_key: str,
        *,
        version: str | None = None,
    ) -> bool:
        if version is None:
            raise AnalyticsUnavailable("analytics_configuration_required")
        return self.outbox_store.is_subject_key_fenced(subject_key, version=version)

    def task_for_name(self, task_name: str) -> DeliveryTask:
        del task_name
        raise AnalyticsUnavailable("Unknown analytics task")

    def delete_subject_keys(
        self,
        subject_keys: set[str],
        fences: list[DeletionFenceRecord],
        *,
        counter_scope_hash: str | None = None,
    ) -> None:
        task_names = self.outbox_store.begin_subject_deletion(subject_keys, fences)
        for task_name in task_names:
            try:
                self.queue.cancel(task_name)
            except AnalyticsDeliveryRetry:
                continue
        try:
            self.warehouse.delete_subject_keys(subject_keys)
            self.outbox_store.finish_subject_deletion(
                subject_keys,
                fences,
                counter_scope_hash=counter_scope_hash,
            )
        except (AnalyticsDeliveryRetry, AnalyticsUnavailable) as error:
            self.outbox_store.mark_deletion_retry(fences)
            raise AnalyticsDeliveryRetry("Transient analytics deletion failure") from error


@dataclass(frozen=True)
class GoogleSdkClients:
    secret_manager: Any
    firestore: Any
    tasks: Any
    bigquery: Any
    verify_google_token: Callable[..., Mapping[str, object]]
    firestore_transactional: Callable[[Callable[..., object]], Callable[..., object]]
    firestore_field_filter_factory: Callable[[str, str, object], object]
    bigquery_scalar_parameter_factory: Callable[[str, str, object], object]
    bigquery_array_parameter_factory: Callable[[str, str, list[str]], object]
    bigquery_job_config_factory: Callable[..., object]
    already_exists_errors: tuple[type[BaseException], ...]
    not_found_errors: tuple[type[BaseException], ...] = ()


@dataclass(frozen=True)
class ProductionAnalyticsBindings:
    analytics_service: AnalyticsService
    task_token_verifier: TaskTokenVerifier


def load_google_sdk_clients(config: ProductionAnalyticsConfig) -> GoogleSdkClients:
    try:
        from google.api_core.exceptions import AlreadyExists, NotFound
        from google.auth.transport.requests import Request
        from google.cloud import bigquery, firestore, secretmanager, tasks_v2
        from google.cloud.firestore_v1.base_query import FieldFilter
        from google.oauth2 import id_token

        auth_request = Request()

        def verify_google_token(
            token: str,
            *,
            audience: str,
        ) -> Mapping[str, object]:
            return id_token.verify_oauth2_token(
                token,
                auth_request,
                audience=audience,
            )

        return GoogleSdkClients(
            secret_manager=secretmanager.SecretManagerServiceClient(),
            firestore=firestore.Client(
                project=config.project_id,
                database=config.firestore_database_id,
            ),
            tasks=tasks_v2.CloudTasksClient(),
            bigquery=bigquery.Client(
                project=config.project_id,
                location=config.location,
            ),
            verify_google_token=verify_google_token,
            firestore_transactional=firestore.transactional,
            firestore_field_filter_factory=FieldFilter,
            bigquery_scalar_parameter_factory=bigquery.ScalarQueryParameter,
            bigquery_array_parameter_factory=bigquery.ArrayQueryParameter,
            bigquery_job_config_factory=bigquery.QueryJobConfig,
            already_exists_errors=(AlreadyExists,),
            not_found_errors=(NotFound,),
        )
    except Exception as error:
        raise AnalyticsUnavailable("analytics_configuration_required") from error


def build_production_analytics(
    settings: Any,
    *,
    clients: GoogleSdkClients | None = None,
) -> ProductionAnalyticsBindings:
    config = production_config_from_settings(settings)
    resolved_clients = clients or load_google_sdk_clients(config)
    keyring = SecretManagerAnalyticsKeyLoader(
        client=resolved_clients.secret_manager,
        config=config,
    ).load()
    gateway = GoogleFirestoreAnalyticsGateway(
        client=resolved_clients.firestore,
        transactional=resolved_clients.firestore_transactional,
        field_filter_factory=resolved_clients.firestore_field_filter_factory,
    )
    outbox = FirestoreAnalyticsOutboxStore(
        gateway=gateway,
        keyring=keyring,
    )
    queue = CloudTasksAnalyticsQueue(
        client=resolved_clients.tasks,
        config=config,
        already_exists_errors=resolved_clients.already_exists_errors,
        not_found_errors=resolved_clients.not_found_errors,
    )
    query_runner = GoogleBigQueryQueryRunner(
        client=resolved_clients.bigquery,
        scalar_parameter_factory=resolved_clients.bigquery_scalar_parameter_factory,
        array_parameter_factory=resolved_clients.bigquery_array_parameter_factory,
        job_config_factory=resolved_clients.bigquery_job_config_factory,
    )
    warehouse = BigQueryAnalyticsWarehouse(
        query_runner=query_runner,
        config=config,
    )
    analytics_service = AnalyticsService(
        project_id=config.project_id,
        environment="production",
        keyring=keyring,
        backend=GoogleAnalyticsBackend(
            outbox=outbox,
            queue=queue,
            warehouse=warehouse,
        ),
        task_audience=config.task_audience,
        task_service_account=config.task_service_account,
    )
    task_token_verifier = GoogleTaskTokenVerifier(
        verify_google_token=resolved_clients.verify_google_token,
        audience=config.task_audience,
        service_account=config.task_service_account,
    )
    return ProductionAnalyticsBindings(
        analytics_service=analytics_service,
        task_token_verifier=task_token_verifier,
    )
