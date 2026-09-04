"""Fail-closed phase controller for manual SC-710 configured evidence.

The controller owns approval, resource, queue-state, and disclosure boundaries. Cloud
operations are injected so this module can be verified with deterministic fakes before a
separately approved Google-backed executor is added.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

from app.analytics import (
    AnalyticsDeliveryRetry,
    AnalyticsReceiptError,
    AnalyticsReceiptRequest,
    DeliveryRequest,
    TaskAuthClaims,
)
from app.analytics_google import (
    DELETION_FENCE_COLLECTION,
    OUTBOX_COLLECTION,
    QUOTA_COUNTER_COLLECTION,
    ProductionAnalyticsConfig,
    build_production_analytics,
    load_google_sdk_clients,
    production_config_from_settings,
)
from app.config import Settings

EXPECTED_PROJECT_ID = "patchamomma-2026-505415"
EXPECTED_LOCATION = "asia-south1"
EXPECTED_FIRESTORE_DATABASE_ID = "(default)"
EXPECTED_PRIVATE_DATASET_ID = "sakhi_analytics"
EXPECTED_ANALYTICS_TABLE_ID = "checkpoint_events_v1"
EXPECTED_QUEUE_ID = "analytics-delivery"
EXPECTED_TASK_SERVICE_ACCOUNT = (
    "sakhi-task-delivery@patchamomma-2026-505415.iam.gserviceaccount.com"
)
EXPECTED_TASK_AUDIENCE = "https://sc710-evidence.invalid/internal/v1/analytics/deliver"
EXPECTED_HMAC_SECRET_NAME = "sakhi-analytics-hmac-key"
EXPECTED_HMAC_SECRET_VERSIONS = ("1",)
MAXIMUM_BYTES_BILLED = 20 * 1024 * 1024
EVIDENCE_FIXTURE_SUBJECT_UID = "sc710-configured-evidence-fixture-v1"
EXPECTED_REPORTING_DATASET_ID = "sakhi_reporting"
EXPECTED_REPORTING_VIEW_ID = "checkpoint_metrics_v1"
EVIDENCE_FIREBASE_APP_ID = "sc710-configured-evidence-cli"


class EvidencePhase(str, Enum):
    PREFLIGHT = "preflight"
    FORGED_REJECTION = "forged-rejection"
    CREATE_SIGNED_FIXTURE = "create-signed-fixture"
    TRANSIENT_WORKER_FAILURE = "transient-worker-failure"
    DELIVER_ONCE = "deliver-once"
    VERIFY_ONE_ROW = "verify-one-row"
    DELETE_FIXTURE = "delete-fixture"
    VERIFY_DELETED = "verify-deleted"


@dataclass(frozen=True)
class ConfiguredEvidenceConfig:
    project_id: str
    location: str
    firestore_database_id: str
    private_dataset_id: str
    analytics_table_id: str
    queue_id: str
    task_service_account: str
    task_audience: str
    hmac_secret_name: str
    hmac_secret_versions: tuple[str, ...]
    current_hmac_secret_version: str
    maximum_bytes_billed: int

    @property
    def queue_path(self) -> str:
        return (
            f"projects/{self.project_id}/locations/{self.location}/"
            f"queues/{self.queue_id}"
        )

    def validate_boundary(self) -> None:
        expected = {
            "project_id": EXPECTED_PROJECT_ID,
            "location": EXPECTED_LOCATION,
            "firestore_database_id": EXPECTED_FIRESTORE_DATABASE_ID,
            "private_dataset_id": EXPECTED_PRIVATE_DATASET_ID,
            "analytics_table_id": EXPECTED_ANALYTICS_TABLE_ID,
            "queue_id": EXPECTED_QUEUE_ID,
            "task_service_account": EXPECTED_TASK_SERVICE_ACCOUNT,
            "task_audience": EXPECTED_TASK_AUDIENCE,
            "hmac_secret_name": EXPECTED_HMAC_SECRET_NAME,
            "hmac_secret_versions": EXPECTED_HMAC_SECRET_VERSIONS,
            "current_hmac_secret_version": "1",
            "maximum_bytes_billed": MAXIMUM_BYTES_BILLED,
        }
        if any(getattr(self, field) != value for field, value in expected.items()):
            raise ValueError("SC-710 configured evidence boundary does not match")


class ConfiguredEvidenceOperations(Protocol):
    def queue_state(self, *, queue_path: str) -> str: ...

    def preflight(
        self,
        *,
        config: ConfiguredEvidenceConfig,
        fixture_subject_uid: str,
    ) -> object: ...

    def forged_rejection(
        self,
        *,
        config: ConfiguredEvidenceConfig,
        fixture_subject_uid: str,
    ) -> object: ...

    def create_signed_fixture(
        self,
        *,
        config: ConfiguredEvidenceConfig,
        fixture_subject_uid: str,
    ) -> object: ...

    def transient_worker_failure(
        self,
        *,
        config: ConfiguredEvidenceConfig,
        fixture_subject_uid: str,
    ) -> object: ...

    def deliver_once(
        self,
        *,
        config: ConfiguredEvidenceConfig,
        fixture_subject_uid: str,
    ) -> object: ...

    def verify_one_row(
        self,
        *,
        config: ConfiguredEvidenceConfig,
        fixture_subject_uid: str,
    ) -> object: ...

    def delete_fixture(
        self,
        *,
        config: ConfiguredEvidenceConfig,
        fixture_subject_uid: str,
    ) -> object: ...

    def verify_deleted(
        self,
        *,
        config: ConfiguredEvidenceConfig,
        fixture_subject_uid: str,
    ) -> object: ...


class GoogleConfiguredEvidenceOperations:
    """Configured evidence orchestration over explicitly injected production boundaries."""

    def __init__(
        self,
        *,
        service_factory: Callable[..., object],
        firestore_gateway: Any,
        tasks_client: Any,
        query_runner: Callable[..., object],
        full_task_view: object,
        task_claims: TaskAuthClaims,
    ) -> None:
        self.service_factory = service_factory
        self.firestore_gateway = firestore_gateway
        self.tasks_client = tasks_client
        self.query_runner = query_runner
        self.full_task_view = full_task_view
        self.task_claims = task_claims

    def queue_state(self, *, queue_path: str) -> str:
        queue = self.tasks_client.get_queue(request={"name": queue_path})
        state = getattr(queue, "state", None)
        state_name = getattr(state, "name", state)
        return str(state_name).upper().rsplit(".", maxsplit=1)[-1]

    def preflight(
        self,
        *,
        config: ConfiguredEvidenceConfig,
        fixture_subject_uid: str,
    ) -> None:
        service, subject_keys, outbox = self._fixture_outbox(
            config,
            fixture_subject_uid,
        )
        del service
        task_names = self._queue_task_names(config)
        row_count = self._fixture_row_count(config, subject_keys)
        if outbox or task_names or row_count != 0:
            raise RuntimeError("configured fixture is not clean")

    def forged_rejection(
        self,
        *,
        config: ConfiguredEvidenceConfig,
        fixture_subject_uid: str,
    ) -> None:
        self._validate_inputs(config, fixture_subject_uid)
        service = self._service(fail_first_warehouse_write=False)
        request = AnalyticsReceiptRequest(
            schemaVersion="analytics-v1.0.0",
            eventId="01a06121-cc00-7b41-8aa4-9ce5f2f6e8d1",
            actionReceipt="v1.forged.forged",
        )
        try:
            service.resume(
                subject_uid=fixture_subject_uid,
                request=request,
            )
        except AnalyticsReceiptError:
            pass
        else:
            raise RuntimeError("forged receipt was accepted")

        subject_keys = self._subject_keys(service, fixture_subject_uid)
        if self._query_outbox(subject_keys) or self._queue_task_names(config):
            raise RuntimeError("forged receipt created an occurrence")

    def create_signed_fixture(
        self,
        *,
        config: ConfiguredEvidenceConfig,
        fixture_subject_uid: str,
    ) -> None:
        self._validate_inputs(config, fixture_subject_uid)
        service = self._service(fail_first_warehouse_write=False)
        issued = service.issue_profile_confirmed(subject_uid=fixture_subject_uid)
        request = AnalyticsReceiptRequest(
            schemaVersion="analytics-v1.0.0",
            eventId=issued.event_id,
            actionReceipt=issued.action_receipt,
        )
        service.resume(subject_uid=fixture_subject_uid, request=request)
        service.resume(subject_uid=fixture_subject_uid, request=request)

        subject_keys = self._subject_keys(service, fixture_subject_uid)
        outbox = self._query_outbox(subject_keys)
        task_names = self._queue_task_names(config)
        self._require_one_outbox_and_task(config, outbox, task_names)

    def transient_worker_failure(
        self,
        *,
        config: ConfiguredEvidenceConfig,
        fixture_subject_uid: str,
    ) -> None:
        _service, _subject_keys, outbox = self._fixture_outbox(
            config,
            fixture_subject_uid,
        )
        delivery_handle = self._task_delivery_handle(config, outbox)
        worker = self._service(fail_first_warehouse_write=True)
        try:
            worker.deliver(delivery_handle, claims=self.task_claims)
        except AnalyticsDeliveryRetry:
            pass
        else:
            raise RuntimeError("transient worker failure was not observed")

        refreshed = self._query_outbox(_subject_keys)
        task_names = self._queue_task_names(config)
        self._require_one_outbox_and_task(config, refreshed, task_names)
        self._task_delivery_handle(config, refreshed)
        document = refreshed[0][1]
        if (
            document.get("deliveryState") != "queued"
            or document.get("attemptCount") != 1
            or not document.get("sealedDeliveryPayload")
        ):
            raise RuntimeError("transient retry state is invalid")

    def deliver_once(
        self,
        *,
        config: ConfiguredEvidenceConfig,
        fixture_subject_uid: str,
    ) -> None:
        _service, subject_keys, outbox = self._fixture_outbox(
            config,
            fixture_subject_uid,
        )
        delivery_handle = self._task_delivery_handle(config, outbox)
        worker = self._service(fail_first_warehouse_write=False)
        result = worker.deliver(delivery_handle, claims=self.task_claims)
        if getattr(result, "status", None) != "written":
            raise RuntimeError("configured delivery did not reach written state")

        refreshed = self._query_outbox(subject_keys)
        if len(refreshed) != 1:
            raise RuntimeError("configured delivery occurrence count is invalid")
        document = refreshed[0][1]
        if (
            document.get("deliveryState") != "written"
            or document.get("sealedDeliveryPayload") is not None
        ):
            raise RuntimeError("configured delivery terminal state is invalid")

    def verify_one_row(
        self,
        *,
        config: ConfiguredEvidenceConfig,
        fixture_subject_uid: str,
    ) -> None:
        self._validate_inputs(config, fixture_subject_uid)
        service = self._service(fail_first_warehouse_write=False)
        subject_keys = self._subject_keys(service, fixture_subject_uid)
        if self._fixture_row_count(config, subject_keys) != 1:
            raise RuntimeError("configured fixture row count is not one")

    def delete_fixture(
        self,
        *,
        config: ConfiguredEvidenceConfig,
        fixture_subject_uid: str,
    ) -> None:
        self._validate_inputs(config, fixture_subject_uid)
        service = self._service(fail_first_warehouse_write=False)
        service.delete_subject(fixture_subject_uid)
        subject_keys = self._subject_keys(service, fixture_subject_uid)
        if self._query_outbox(subject_keys) or self._queue_task_names(config):
            raise RuntimeError("configured fixture cleanup is incomplete")

    def verify_deleted(
        self,
        *,
        config: ConfiguredEvidenceConfig,
        fixture_subject_uid: str,
    ) -> None:
        self._validate_inputs(config, fixture_subject_uid)
        service = self._service(fail_first_warehouse_write=False)
        subject_keys_by_version = service.keyring.subject_keys_for_deletion(
            fixture_subject_uid
        )
        subject_keys = sorted(subject_keys_by_version.values())
        outbox = self._query_outbox(subject_keys)
        counters = self.firestore_gateway.query_documents(
            collection=QUOTA_COUNTER_COLLECTION,
            filters=[
                ("scopeKind", "==", "subject"),
                (
                    "scopeHash",
                    "==",
                    hashlib.sha256(fixture_subject_uid.encode()).hexdigest(),
                ),
            ],
        )
        tasks = self._queue_task_names(config)
        row_count = self._fixture_row_count(config, subject_keys)
        fences = [
            self.firestore_gateway.get_document(
                collection=DELETION_FENCE_COLLECTION,
                document_id=service.keyring.deletion_fence_key(
                    fixture_subject_uid,
                    version=version,
                ),
            )
            for version in subject_keys_by_version
        ]
        if outbox or counters or tasks or row_count != 0 or not fences:
            raise RuntimeError("configured fixture deletion is incomplete")
        for fence in fences:
            if (
                not isinstance(fence, dict)
                or set(fence) != {"expiresAt", "deletionState"}
                or fence.get("expiresAt") is None
                or fence.get("deletionState") != "complete"
            ):
                raise RuntimeError("configured fixture deletion is incomplete")

    def _validate_inputs(
        self,
        config: ConfiguredEvidenceConfig,
        fixture_subject_uid: str,
    ) -> None:
        config.validate_boundary()
        if fixture_subject_uid != EVIDENCE_FIXTURE_SUBJECT_UID:
            raise ValueError("SC-710 configured evidence fixture does not match")

    def _service(self, *, fail_first_warehouse_write: bool) -> Any:
        return self.service_factory(
            fail_first_warehouse_write=fail_first_warehouse_write,
        )

    def _fixture_outbox(
        self,
        config: ConfiguredEvidenceConfig,
        fixture_subject_uid: str,
    ) -> tuple[Any, list[str], list[tuple[str, dict[str, object]]]]:
        self._validate_inputs(config, fixture_subject_uid)
        service = self._service(fail_first_warehouse_write=False)
        subject_keys = self._subject_keys(service, fixture_subject_uid)
        return service, subject_keys, self._query_outbox(subject_keys)

    @staticmethod
    def _subject_keys(service: Any, fixture_subject_uid: str) -> list[str]:
        values = service.keyring.subject_keys_for_deletion(fixture_subject_uid).values()
        return sorted(values)

    def _query_outbox(
        self,
        subject_keys: list[str],
    ) -> list[tuple[str, dict[str, object]]]:
        return self.firestore_gateway.query_documents(
            collection=OUTBOX_COLLECTION,
            filters=[("subjectKey", "in", subject_keys)],
        )

    def _queue_task_names(self, config: ConfiguredEvidenceConfig) -> list[str]:
        tasks = self.tasks_client.list_tasks(
            request={"parent": config.queue_path},
        )
        names = [getattr(task, "name", None) for task in tasks]
        if not all(isinstance(name, str) and name for name in names):
            raise RuntimeError("configured task metadata is invalid")
        return sorted(names)

    @staticmethod
    def _full_task_name(config: ConfiguredEvidenceConfig, task_name: str) -> str:
        if task_name.startswith("projects/"):
            return task_name
        return f"{config.queue_path}/tasks/{task_name}"

    def _require_one_outbox_and_task(
        self,
        config: ConfiguredEvidenceConfig,
        outbox: list[tuple[str, dict[str, object]]],
        task_names: list[str],
    ) -> None:
        if len(outbox) != 1 or len(task_names) != 1:
            raise RuntimeError("configured fixture occurrence count is invalid")
        stored_task_name = outbox[0][1].get("taskName")
        if not isinstance(stored_task_name, str):
            raise TypeError("configured fixture task name is invalid")
        if task_names[0] != self._full_task_name(config, stored_task_name):
            raise RuntimeError("configured fixture task name is invalid")

    def _task_delivery_handle(
        self,
        config: ConfiguredEvidenceConfig,
        outbox: list[tuple[str, dict[str, object]]],
    ) -> str:
        if len(outbox) != 1:
            raise RuntimeError("configured fixture occurrence count is invalid")
        task_name = outbox[0][1].get("taskName")
        if not isinstance(task_name, str):
            raise TypeError("configured fixture task name is invalid")
        task = self.tasks_client.get_task(
            request={
                "name": self._full_task_name(config, task_name),
                "response_view": self.full_task_view,
            }
        )
        raw_body = getattr(getattr(task, "http_request", None), "body", None)
        try:
            if not isinstance(raw_body, (bytes, bytearray, str)):
                raise TypeError("Task body is missing")
            body = json.loads(raw_body)
            if not isinstance(body, dict) or set(body) != {"deliveryHandle"}:
                raise ValueError("Task body fields do not match")
            return DeliveryRequest.model_validate(body).delivery_handle
        except Exception as error:
            raise RuntimeError("opaque task body is invalid") from error

    def _fixture_row_count(
        self,
        config: ConfiguredEvidenceConfig,
        subject_keys: list[str],
    ) -> int:
        table = (
            f"{config.project_id}.{config.private_dataset_id}."
            f"{config.analytics_table_id}"
        )
        query = f"""\
SELECT COUNT(*) AS row_count
FROM `{table}`
WHERE event_date >= DATE_SUB(CURRENT_DATE("Asia/Kolkata"), INTERVAL 90 DAY)
  AND subject_key IN UNNEST(@subject_keys)
"""
        result = self.query_runner(
            query=query,
            parameters={"subject_keys": subject_keys},
            maximum_bytes_billed=config.maximum_bytes_billed,
            location=config.location,
        )
        try:
            rows = list(result)
            row_count = rows[0]["row_count"]
            if len(rows) != 1 or not isinstance(row_count, int) or isinstance(row_count, bool):
                raise ValueError("Invalid aggregate count")
            return row_count
        except Exception as error:
            raise RuntimeError("configured fixture count is invalid") from error


PHASE_METHODS = {
    EvidencePhase.PREFLIGHT: "preflight",
    EvidencePhase.FORGED_REJECTION: "forged_rejection",
    EvidencePhase.CREATE_SIGNED_FIXTURE: "create_signed_fixture",
    EvidencePhase.TRANSIENT_WORKER_FAILURE: "transient_worker_failure",
    EvidencePhase.DELIVER_ONCE: "deliver_once",
    EvidencePhase.VERIFY_ONE_ROW: "verify_one_row",
    EvidencePhase.DELETE_FIXTURE: "delete_fixture",
    EvidencePhase.VERIFY_DELETED: "verify_deleted",
}


def confirmation_phrase(phase: EvidencePhase, project_id: str) -> str:
    phase_value = phase.value if isinstance(phase, EvidencePhase) else EvidencePhase(phase).value
    return f"CONFIRM SC-710 {phase_value} {project_id}"


def configured_evidence_config(project_id: str) -> ConfiguredEvidenceConfig:
    return ConfiguredEvidenceConfig(
        project_id=project_id,
        location=EXPECTED_LOCATION,
        firestore_database_id=EXPECTED_FIRESTORE_DATABASE_ID,
        private_dataset_id=EXPECTED_PRIVATE_DATASET_ID,
        analytics_table_id=EXPECTED_ANALYTICS_TABLE_ID,
        queue_id=EXPECTED_QUEUE_ID,
        task_service_account=EXPECTED_TASK_SERVICE_ACCOUNT,
        task_audience=EXPECTED_TASK_AUDIENCE,
        hmac_secret_name=EXPECTED_HMAC_SECRET_NAME,
        hmac_secret_versions=EXPECTED_HMAC_SECRET_VERSIONS,
        current_hmac_secret_version="1",
        maximum_bytes_billed=MAXIMUM_BYTES_BILLED,
    )


def _production_settings(config: ConfiguredEvidenceConfig) -> Settings:
    config.validate_boundary()
    return Settings(
        app_env="production",
        adapter_mode="production",
        paid_api_calls_enabled=False,
        firebase_project_id=config.project_id,
        firebase_app_id=EVIDENCE_FIREBASE_APP_ID,
        firestore_database_id=config.firestore_database_id,
        analytics_location=config.location,
        analytics_private_dataset_id=config.private_dataset_id,
        analytics_table_id=config.analytics_table_id,
        analytics_reporting_dataset_id=EXPECTED_REPORTING_DATASET_ID,
        analytics_reporting_view_id=EXPECTED_REPORTING_VIEW_ID,
        analytics_queue_id=config.queue_id,
        analytics_task_service_account=config.task_service_account,
        analytics_task_audience=config.task_audience,
        analytics_hmac_secret_name=config.hmac_secret_name,
        analytics_hmac_secret_versions=list(config.hmac_secret_versions),
        analytics_current_hmac_secret_version=config.current_hmac_secret_version,
    )


class _FailFirstQueryRunner:
    def __init__(self, delegate: Callable[..., object]) -> None:
        self.delegate = delegate
        self.failed = False

    def __call__(self, **values: object) -> object:
        if not self.failed:
            self.failed = True
            raise RuntimeError("SC-710 intentional transient warehouse failure")
        return self.delegate(**values)


def build_google_configured_evidence_operations(
    *,
    project_id: str,
    sdk_loader: Callable[[ProductionAnalyticsConfig], object] = load_google_sdk_clients,
    analytics_builder: Callable[..., object] = build_production_analytics,
    full_task_view: object | None = None,
) -> GoogleConfiguredEvidenceOperations:
    config = configured_evidence_config(project_id)
    config.validate_boundary()
    settings = _production_settings(config)
    production_config = production_config_from_settings(settings)
    clients = sdk_loader(production_config)
    first_bindings = analytics_builder(settings, clients=clients)
    first_service = first_bindings.analytics_service
    services = [first_service]

    def service_factory(*, fail_first_warehouse_write: bool) -> object:
        if services:
            service = services.pop()
        else:
            service = analytics_builder(settings, clients=clients).analytics_service
        if fail_first_warehouse_write:
            warehouse = service.backend.warehouse
            warehouse.query_runner = _FailFirstQueryRunner(warehouse.query_runner)
        return service

    if full_task_view is None:
        from google.cloud.tasks_v2.types import Task

        full_task_view = Task.View.FULL

    backend = first_service.backend
    return GoogleConfiguredEvidenceOperations(
        service_factory=service_factory,
        firestore_gateway=backend.outbox_store.gateway,
        tasks_client=clients.tasks,
        query_runner=backend.warehouse.query_runner,
        full_task_view=full_task_view,
        task_claims=TaskAuthClaims(
            issuer="https://accounts.google.com",
            audience=config.task_audience,
            serviceAccount=config.task_service_account,
        ),
    )


def _execute_confirmed_phase(
    *,
    config: ConfiguredEvidenceConfig,
    phase: EvidencePhase,
    operations: ConfiguredEvidenceOperations,
    output_fn: Callable[[str], None],
) -> bool:
    try:
        queue_state = operations.queue_state(queue_path=config.queue_path)
    except Exception:  # noqa: BLE001 - evidence output must suppress client error content.
        output_fn(f"SC-710 {phase.value}: FAIL")
        return False
    if queue_state != "PAUSED":
        output_fn(f"SC-710 {phase.value}: BLOCKED (queue must be PAUSED)")
        return False

    operation_name = PHASE_METHODS[phase]
    operation = getattr(operations, operation_name)
    try:
        operation(
            config=config,
            fixture_subject_uid=EVIDENCE_FIXTURE_SUBJECT_UID,
        )
    except Exception:  # noqa: BLE001 - evidence output must suppress client error content.
        output_fn(f"SC-710 {phase.value}: FAIL")
        return False

    output_fn(f"SC-710 {phase.value}: PASS")
    return True


def execute_phase(
    *,
    config: ConfiguredEvidenceConfig,
    phase: EvidencePhase,
    operations: ConfiguredEvidenceOperations,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
) -> bool:
    config.validate_boundary()
    expected_confirmation = confirmation_phrase(phase, config.project_id)
    supplied_confirmation = input_fn(
        f"Type '{expected_confirmation}' to run this one evidence phase: "
    )
    if supplied_confirmation != expected_confirmation:
        output_fn(f"SC-710 {phase.value}: CANCELLED")
        return False

    return _execute_confirmed_phase(
        config=config,
        phase=phase,
        operations=operations,
        output_fn=output_fn,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one separately approved SC-710 configured-evidence phase.",
    )
    parser.add_argument(
        "--phase",
        required=True,
        type=EvidencePhase,
        choices=tuple(EvidencePhase),
    )
    parser.add_argument("--project", required=True)
    return parser


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    operations_factory: Callable[
        [ConfiguredEvidenceConfig], ConfiguredEvidenceOperations
    ]
    | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = configured_evidence_config(args.project)
    config.validate_boundary()
    phase = args.phase
    expected_confirmation = confirmation_phrase(phase, config.project_id)
    supplied_confirmation = input_fn(
        f"Type '{expected_confirmation}' to run this one evidence phase: "
    )
    if supplied_confirmation != expected_confirmation:
        output_fn(f"SC-710 {phase.value}: CANCELLED")
        return 1

    resolved_factory = operations_factory or (
        lambda selected: build_google_configured_evidence_operations(
            project_id=selected.project_id,
        )
    )
    try:
        operations = resolved_factory(config)
    except Exception:  # noqa: BLE001 - evidence output must suppress client error content.
        output_fn(f"SC-710 {phase.value}: FAIL")
        return 1

    succeeded = _execute_confirmed_phase(
        config=config,
        phase=phase,
        operations=operations,
        output_fn=output_fn,
    )
    return 0 if succeeded else 1


def main(argv: Sequence[str] | None = None) -> int:
    return run_cli(argv)


if __name__ == "__main__":
    raise SystemExit(main())
