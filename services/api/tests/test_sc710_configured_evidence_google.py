import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.analytics import AnalyticsDeliveryRetry, AnalyticsReceiptError, TaskAuthClaims
from scripts.sc710_configured_evidence import (
    EVIDENCE_FIXTURE_SUBJECT_UID,
    MAXIMUM_BYTES_BILLED,
    ConfiguredEvidenceConfig,
    GoogleConfiguredEvidenceOperations,
)

PROJECT_ID = "patchamomma-2026-505415"
LOCATION = "asia-south1"
TASK_IDENTITY = (
    "sakhi-task-delivery@patchamomma-2026-505415.iam.gserviceaccount.com"
)
TASK_AUDIENCE = "https://sc710-evidence.invalid/internal/v1/analytics/deliver"
EVENT_ID = "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d1"
TASK_NAME = (
    "projects/patchamomma-2026-505415/locations/asia-south1/"
    "queues/analytics-delivery/tasks/task-name-canary"
)
SUBJECT_KEY = "subject-key-canary"
FENCE_KEY = "fence-key-canary"
DELIVERY_HANDLE = "opaque-delivery-handle-canary-0001"


def evidence_config() -> ConfiguredEvidenceConfig:
    return ConfiguredEvidenceConfig(
        project_id=PROJECT_ID,
        location=LOCATION,
        firestore_database_id="(default)",
        private_dataset_id="sakhi_analytics",
        analytics_table_id="checkpoint_events_v1",
        queue_id="analytics-delivery",
        task_service_account=TASK_IDENTITY,
        task_audience=TASK_AUDIENCE,
        hmac_secret_name="sakhi-analytics-hmac-key",
        hmac_secret_versions=("1",),
        current_hmac_secret_version="1",
        maximum_bytes_billed=MAXIMUM_BYTES_BILLED,
    )


class FakeKeyring:
    def subject_keys_for_deletion(self, subject_uid: str) -> dict[str, str]:
        assert subject_uid == EVIDENCE_FIXTURE_SUBJECT_UID
        return {"1": SUBJECT_KEY}

    def deletion_fence_key(self, subject_uid: str, *, version: str) -> str:
        assert subject_uid == EVIDENCE_FIXTURE_SUBJECT_UID
        assert version == "1"
        return FENCE_KEY


class FakeService:
    def __init__(self, rig: "Rig", *, fail_first_warehouse_write: bool) -> None:
        self.rig = rig
        self.fail_first_warehouse_write = fail_first_warehouse_write
        self.keyring = FakeKeyring()

    def resume(self, *, subject_uid: str, request: object) -> object:
        self.rig.service_calls.append(("resume", subject_uid, request))
        if self.rig.forged_receipt:
            raise AnalyticsReceiptError("secret receipt error must not escape")
        return SimpleNamespace(status="queued")

    def issue_profile_confirmed(self, *, subject_uid: str) -> object:
        self.rig.service_calls.append(("issue_profile_confirmed", subject_uid))
        return SimpleNamespace(event_id=EVENT_ID, action_receipt="receipt-canary")

    def deliver(self, delivery_handle: str, *, claims: TaskAuthClaims) -> object:
        self.rig.service_calls.append(("deliver", delivery_handle, claims))
        if self.fail_first_warehouse_write:
            raise AnalyticsDeliveryRetry("transient failure canary")
        return SimpleNamespace(status="written")

    def delete_subject(self, subject_uid: str) -> None:
        self.rig.service_calls.append(("delete_subject", subject_uid))


class FakeFirestoreGateway:
    def __init__(self, rig: "Rig") -> None:
        self.rig = rig

    def query_documents(
        self,
        *,
        collection: str,
        filters: list[tuple[str, str, object]],
        limit: int | None = None,
    ) -> list[tuple[str, dict[str, object]]]:
        self.rig.firestore_calls.append(("query", collection, filters, limit))
        if collection == "analytics_outbox_v1":
            return self.rig.outbox_documents
        if collection == "runtime_quota_counters_v1":
            return self.rig.counter_documents
        raise AssertionError(f"unexpected collection: {collection}")

    def get_document(self, *, collection: str, document_id: str) -> dict[str, object] | None:
        self.rig.firestore_calls.append(("get", collection, document_id))
        if collection != "analytics_deletion_fences_v1" or document_id != FENCE_KEY:
            raise AssertionError("unexpected fence read")
        return self.rig.fence_document


class FakeTasksClient:
    def __init__(self, rig: "Rig") -> None:
        self.rig = rig

    def get_queue(self, *, request: dict[str, str]) -> object:
        self.rig.task_calls.append(("get_queue", request))
        return SimpleNamespace(state=SimpleNamespace(name=self.rig.queue_state))

    def list_tasks(self, *, request: dict[str, object]) -> list[object]:
        self.rig.task_calls.append(("list_tasks", request))
        return [SimpleNamespace(name=name) for name in self.rig.task_names]

    def get_task(self, *, request: dict[str, object]) -> object:
        self.rig.task_calls.append(("get_task", request))
        return SimpleNamespace(
            http_request=SimpleNamespace(
                body=json.dumps(self.rig.task_body).encode(),
            )
        )


class Rig:
    def __init__(self) -> None:
        self.queue_state = "PAUSED"
        self.forged_receipt = False
        self.row_count = 0
        self.outbox_documents: list[tuple[str, dict[str, object]]] = []
        self.counter_documents: list[tuple[str, dict[str, object]]] = []
        self.fence_document: dict[str, object] | None = None
        self.task_names: list[str] = []
        self.task_body: dict[str, object] = {"deliveryHandle": DELIVERY_HANDLE}
        self.service_calls: list[tuple[Any, ...]] = []
        self.firestore_calls: list[tuple[Any, ...]] = []
        self.task_calls: list[tuple[Any, ...]] = []
        self.query_calls: list[dict[str, object]] = []
        self.service_factory_calls: list[bool] = []

        def service_factory(*, fail_first_warehouse_write: bool) -> FakeService:
            self.service_factory_calls.append(fail_first_warehouse_write)
            return FakeService(
                self,
                fail_first_warehouse_write=fail_first_warehouse_write,
            )

        def query_runner(**call: object) -> list[dict[str, int]]:
            self.query_calls.append(call)
            return [{"row_count": self.row_count}]

        self.operations = GoogleConfiguredEvidenceOperations(
            service_factory=service_factory,
            firestore_gateway=FakeFirestoreGateway(self),
            tasks_client=FakeTasksClient(self),
            query_runner=query_runner,
            full_task_view="FULL",
            task_claims=TaskAuthClaims(
                issuer="https://accounts.google.com",
                audience=TASK_AUDIENCE,
                serviceAccount=TASK_IDENTITY,
            ),
        )

    def queued_outbox(self, *, attempts: int = 0) -> None:
        self.outbox_documents = [
            (
                "event-key-canary",
                {
                    "subjectKey": SUBJECT_KEY,
                    "taskName": "task-name-canary",
                    "deliveryState": "queued",
                    "attemptCount": attempts,
                    "sealedDeliveryPayload": "sealed-payload-canary",
                },
            )
        ]
        self.task_names = [TASK_NAME]

    def written_outbox(self) -> None:
        self.outbox_documents = [
            (
                "event-key-canary",
                {
                    "subjectKey": SUBJECT_KEY,
                    "taskName": "task-name-canary",
                    "deliveryState": "written",
                    "attemptCount": 2,
                    "sealedDeliveryPayload": None,
                },
            )
        ]
        self.task_names = [TASK_NAME]


def _assert_capped_fixture_count_query(rig: Rig) -> None:
    assert len(rig.query_calls) == 1
    call = rig.query_calls[0]
    query = str(call["query"])
    assert "SELECT COUNT(*) AS row_count" in query
    assert f"`{PROJECT_ID}.sakhi_analytics.checkpoint_events_v1`" in query
    assert 'CURRENT_DATE("Asia/Kolkata")' in query
    assert "INTERVAL 90 DAY" in query
    assert "subject_key IN UNNEST(@subject_keys)" in query
    assert call["parameters"] == {"subject_keys": [SUBJECT_KEY]}
    assert call["maximum_bytes_billed"] == MAXIMUM_BYTES_BILLED
    assert call["location"] == LOCATION


def test_constructor_is_inert_and_queue_state_reads_only_the_exact_queue() -> None:
    rig = Rig()

    assert rig.service_factory_calls == []
    assert rig.firestore_calls == []
    assert rig.task_calls == []
    assert rig.query_calls == []

    state = rig.operations.queue_state(queue_path=evidence_config().queue_path)

    assert state == "PAUSED"
    assert rig.task_calls == [
        ("get_queue", {"name": evidence_config().queue_path}),
    ]


@pytest.mark.parametrize("stale_resource", ("outbox", "task", "row"))
def test_preflight_uses_one_capped_count_and_refuses_every_stale_fixture(
    stale_resource: str,
) -> None:
    rig = Rig()
    if stale_resource == "outbox":
        rig.queued_outbox()
        rig.task_names = []
    elif stale_resource == "task":
        rig.task_names = [TASK_NAME]
    else:
        rig.row_count = 1

    with pytest.raises(RuntimeError, match="configured fixture is not clean"):
        rig.operations.preflight(
            config=evidence_config(),
            fixture_subject_uid=EVIDENCE_FIXTURE_SUBJECT_UID,
        )

    _assert_capped_fixture_count_query(rig)


def test_clean_preflight_reads_no_row_or_task_payload() -> None:
    rig = Rig()

    rig.operations.preflight(
        config=evidence_config(),
        fixture_subject_uid=EVIDENCE_FIXTURE_SUBJECT_UID,
    )

    _assert_capped_fixture_count_query(rig)
    assert not any(call[0] == "get_task" for call in rig.task_calls)


def test_forged_receipt_is_rejected_before_any_occurrence_or_task_exists() -> None:
    rig = Rig()
    rig.forged_receipt = True

    rig.operations.forged_rejection(
        config=evidence_config(),
        fixture_subject_uid=EVIDENCE_FIXTURE_SUBJECT_UID,
    )

    assert [call[0] for call in rig.service_calls] == ["resume"]
    assert rig.outbox_documents == []
    assert rig.task_names == []
    assert rig.query_calls == []


def test_signed_fixture_issues_once_and_replays_the_identical_receipt_twice() -> None:
    rig = Rig()
    rig.queued_outbox()

    rig.operations.create_signed_fixture(
        config=evidence_config(),
        fixture_subject_uid=EVIDENCE_FIXTURE_SUBJECT_UID,
    )

    assert [call[0] for call in rig.service_calls] == [
        "issue_profile_confirmed",
        "resume",
        "resume",
    ]
    first_request = rig.service_calls[1][2]
    second_request = rig.service_calls[2][2]
    assert first_request == second_request
    assert first_request.event_id == EVENT_ID
    assert first_request.action_receipt == "receipt-canary"
    assert rig.query_calls == []


def test_transient_worker_failure_reads_only_opaque_task_body_and_persists_retry() -> None:
    rig = Rig()
    rig.queued_outbox(attempts=1)

    rig.operations.transient_worker_failure(
        config=evidence_config(),
        fixture_subject_uid=EVIDENCE_FIXTURE_SUBJECT_UID,
    )

    assert rig.service_factory_calls == [False, True]
    assert rig.service_calls[-1] == (
        "deliver",
        DELIVERY_HANDLE,
        rig.operations.task_claims,
    )
    assert rig.task_calls[-1] == (
        "get_task",
        {"name": TASK_NAME, "response_view": "FULL"},
    )
    assert rig.query_calls == []


@pytest.mark.parametrize(
    "body",
    (
        {},
        {"deliveryHandle": "short"},
        {"deliveryHandle": DELIVERY_HANDLE, "eventId": EVENT_ID},
    ),
)
def test_worker_phases_reject_missing_short_or_expanded_task_bodies(body: dict[str, object]) -> None:
    rig = Rig()
    rig.queued_outbox(attempts=1)
    rig.task_body = body

    with pytest.raises(RuntimeError, match="opaque task body is invalid"):
        rig.operations.deliver_once(
            config=evidence_config(),
            fixture_subject_uid=EVIDENCE_FIXTURE_SUBJECT_UID,
        )

    assert not any(call[0] == "deliver" for call in rig.service_calls)


def test_delivery_rebuilds_service_and_requires_written_terminal_state() -> None:
    rig = Rig()
    rig.written_outbox()

    rig.operations.deliver_once(
        config=evidence_config(),
        fixture_subject_uid=EVIDENCE_FIXTURE_SUBJECT_UID,
    )

    assert rig.service_factory_calls == [False, False]
    assert [call[0] for call in rig.service_calls] == ["deliver"]
    assert rig.query_calls == []


def test_one_row_verification_returns_only_an_aggregate_count_under_the_cap() -> None:
    rig = Rig()
    rig.row_count = 1

    rig.operations.verify_one_row(
        config=evidence_config(),
        fixture_subject_uid=EVIDENCE_FIXTURE_SUBJECT_UID,
    )

    _assert_capped_fixture_count_query(rig)
    assert not any("event_id" in str(value) for value in rig.query_calls)


def test_delete_fixture_uses_the_production_subject_deletion_path() -> None:
    rig = Rig()
    rig.outbox_documents = []
    rig.task_names = []

    rig.operations.delete_fixture(
        config=evidence_config(),
        fixture_subject_uid=EVIDENCE_FIXTURE_SUBJECT_UID,
    )

    assert rig.service_factory_calls == [False]
    assert rig.service_calls == [
        ("delete_subject", EVIDENCE_FIXTURE_SUBJECT_UID),
    ]
    assert rig.query_calls == []


def test_final_verification_requires_zero_linkable_state_and_complete_fence() -> None:
    rig = Rig()
    rig.fence_document = {
        "expiresAt": "server-timestamp-canary",
        "deletionState": "complete",
    }

    rig.operations.verify_deleted(
        config=evidence_config(),
        fixture_subject_uid=EVIDENCE_FIXTURE_SUBJECT_UID,
    )

    _assert_capped_fixture_count_query(rig)
    assert rig.outbox_documents == []
    assert rig.counter_documents == []
    assert rig.task_names == []
    assert rig.fence_document == {
        "expiresAt": "server-timestamp-canary",
        "deletionState": "complete",
    }
