import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from app.analytics import (
    AnalyticsDeliveryRetry,
    AnalyticsKeyring,
    AnalyticsReceiptRequest,
    AnalyticsService,
    TaskAuthClaims,
)
from app.analytics_google import (
    OUTBOX_COLLECTION,
    BigQueryAnalyticsWarehouse,
    CloudTasksAnalyticsQueue,
    FirestoreAnalyticsOutboxStore,
    GoogleAnalyticsBackend,
    GoogleFirestoreAnalyticsGateway,
    ProductionAnalyticsConfig,
)

NOW = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)
EVENT_ID_1 = "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d1"
EVENT_ID_2 = "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d2"
SUBJECT_UID = "firebase-user"
TASK_AUDIENCE = "https://api.example.test/internal/v1/analytics/deliver"
TASK_IDENTITY = "sakhi-task-delivery@test-project.iam.gserviceaccount.com"

CONFIG = ProductionAnalyticsConfig(
    projectId="test-project",
    firestoreDatabaseId="(default)",
    location="asia-south1",
    privateDatasetId="sakhi_analytics",
    analyticsTableId="checkpoint_events_v1",
    reportingDatasetId="sakhi_reporting",
    reportingViewId="checkpoint_metrics_v1",
    queueId="analytics-delivery",
    taskServiceAccount=TASK_IDENTITY,
    taskAudience=TASK_AUDIENCE,
    hmacSecretName="sakhi-analytics-hmac-key",
    hmacSecretVersions=["7", "8"],
    currentHmacSecretVersion="8",
)


class AlreadyExistsForTest(Exception):
    pass


class NotFoundForTest(Exception):
    pass


class FakeSnapshot:
    def __init__(self, reference: "FakeDocumentReference") -> None:
        self.reference = reference
        self.id = reference.id
        self.exists = reference.document is not None
        self._document = deepcopy(reference.document)

    def to_dict(self) -> dict[str, object] | None:
        return deepcopy(self._document)


class FakeDocumentReference:
    def __init__(self, collection: "FakeCollection", document_id: str) -> None:
        self.collection = collection
        self.id = document_id
        self.document: dict[str, object] | None = None

    @property
    def path(self) -> str:
        return f"{self.collection.name}/{self.id}"

    def get(self, *, transaction: object | None = None) -> FakeSnapshot:
        del transaction
        return FakeSnapshot(self)

    def set(self, document: dict[str, object], *, merge: bool = False) -> None:
        with self.collection.client.lock:
            if merge and self.document is not None:
                self.document.update(deepcopy(document))
            else:
                self.document = deepcopy(document)
            self.collection.client.log.append(f"firestore:set:{self.path}")

    def update(self, document: dict[str, object]) -> None:
        with self.collection.client.lock:
            if self.document is None:
                raise NotFoundForTest(self.path)
            self.document.update(deepcopy(document))
            self.collection.client.log.append(f"firestore:update:{self.path}")

    def delete(self) -> None:
        with self.collection.client.lock:
            self.document = None
            self.collection.client.log.append(f"firestore:delete:{self.path}")


class FakeQuery:
    def __init__(
        self,
        collection: "FakeCollection",
        filters: list[tuple[str, str, object]] | None = None,
        limit_value: int | None = None,
    ) -> None:
        self.collection = collection
        self.filters = filters or []
        self.limit_value = limit_value

    def where(self, *, filter: tuple[str, str, object]) -> "FakeQuery":
        return FakeQuery(self.collection, [*self.filters, filter], self.limit_value)

    def limit(self, value: int) -> "FakeQuery":
        return FakeQuery(self.collection, self.filters, value)

    def stream(self, *, transaction: object | None = None) -> list[FakeSnapshot]:
        del transaction
        snapshots = [
            FakeSnapshot(reference)
            for reference in self.collection.references.values()
            if reference.document is not None and self._matches(reference.document)
        ]
        return snapshots[: self.limit_value]

    def _matches(self, document: dict[str, object]) -> bool:
        for field, operator, expected in self.filters:
            actual = document.get(field)
            if operator == "==" and actual != expected:
                return False
            if operator == "in" and actual not in expected:
                return False
            if operator == "array_contains_any" and (
                not isinstance(actual, list) or not set(actual).intersection(expected)
            ):
                return False
        return True


class FakeCollection(FakeQuery):
    def __init__(self, client: "FakeFirestoreClient", name: str) -> None:
        self.client = client
        self.name = name
        self.references: dict[str, FakeDocumentReference] = {}
        super().__init__(self)

    def document(self, document_id: str) -> FakeDocumentReference:
        return self.references.setdefault(
            document_id,
            FakeDocumentReference(self, document_id),
        )


class FakeTransaction:
    def __init__(self, client: "FakeFirestoreClient") -> None:
        self.client = client

    def get(self, target: FakeDocumentReference | FakeQuery):
        if isinstance(target, FakeDocumentReference):
            return target.get(transaction=self)
        return target.stream(transaction=self)

    def create(
        self,
        reference: FakeDocumentReference,
        document: dict[str, object],
    ) -> None:
        if reference.document is not None:
            raise AlreadyExistsForTest(reference.path)
        reference.document = deepcopy(document)
        self.client.log.append(f"firestore:create:{reference.path}")

    def set(
        self,
        reference: FakeDocumentReference,
        document: dict[str, object],
        *,
        merge: bool = False,
    ) -> None:
        if merge and reference.document is not None:
            reference.document.update(deepcopy(document))
        else:
            reference.document = deepcopy(document)
        self.client.log.append(f"firestore:set:{reference.path}")

    def update(
        self,
        reference: FakeDocumentReference,
        document: dict[str, object],
    ) -> None:
        if reference.document is None:
            raise NotFoundForTest(reference.path)
        reference.document.update(deepcopy(document))
        self.client.log.append(f"firestore:update:{reference.path}")

    def delete(self, reference: FakeDocumentReference) -> None:
        reference.document = None
        self.client.log.append(f"firestore:delete:{reference.path}")


class FakeBatch(FakeTransaction):
    def commit(self) -> None:
        self.client.log.append("firestore:batch:commit")


class FakeFirestoreClient:
    def __init__(self, log: list[str]) -> None:
        self.log = log
        self.lock = threading.RLock()
        self.collections: dict[str, FakeCollection] = {}

    def collection(self, name: str) -> FakeCollection:
        return self.collections.setdefault(name, FakeCollection(self, name))

    def transaction(self) -> FakeTransaction:
        return FakeTransaction(self)

    def batch(self) -> FakeBatch:
        return FakeBatch(self)

    def transactional(self, function):
        def run(transaction: FakeTransaction):
            with self.lock:
                return function(transaction)

        return run


class FakeTasksClient:
    def __init__(self, log: list[str]) -> None:
        self.log = log
        self.tasks: dict[str, dict[str, object]] = {}

    def create_task(self, *, request: dict[str, object]) -> None:
        task = request["task"]
        assert isinstance(task, dict)
        name = str(task["name"])
        if name in self.tasks:
            raise AlreadyExistsForTest(name)
        self.tasks[name] = deepcopy(task)
        self.log.append(f"tasks:create:{name}")

    def delete_task(self, *, request: dict[str, str]) -> None:
        name = request["name"]
        if name not in self.tasks:
            raise NotFoundForTest(name)
        self.tasks.pop(name)
        self.log.append(f"tasks:delete:{name}")


class FakeQueryRunner:
    def __init__(self, log: list[str]) -> None:
        self.log = log
        self.calls: list[dict[str, object]] = []
        self.fail_writes = 0
        self.fail_deletes = 0

    def __call__(self, **request: object) -> list[object]:
        self.calls.append(request)
        query = str(request["query"]).lstrip()
        operation = "delete" if query.startswith("DELETE") else "merge"
        self.log.append(f"bigquery:{operation}")
        if operation == "delete" and self.fail_deletes:
            self.fail_deletes -= 1
            raise RuntimeError("transient deletion failure")
        if operation == "merge" and self.fail_writes:
            self.fail_writes -= 1
            raise RuntimeError("transient write failure")
        return []


class ProductionRig:
    def __init__(self) -> None:
        self.log: list[str] = []
        self.firestore = FakeFirestoreClient(self.log)
        self.tasks = FakeTasksClient(self.log)
        self.queries = FakeQueryRunner(self.log)
        self.keyring = AnalyticsKeyring(
            project_id="test-project",
            keys={
                "7": b"older-test-key-material-32-byte",
                "8": b"newer-test-key-material-32-byte",
            },
            current_version="8",
        )

    def make_service(self, *, event_id: str = EVENT_ID_1) -> AnalyticsService:
        gateway = GoogleFirestoreAnalyticsGateway(
            client=self.firestore,
            transactional=self.firestore.transactional,
            field_filter_factory=lambda field, operator, value: (
                field,
                operator,
                value,
            ),
        )
        backend = GoogleAnalyticsBackend(
            outbox=FirestoreAnalyticsOutboxStore(
                gateway=gateway,
                keyring=self.keyring,
            ),
            queue=CloudTasksAnalyticsQueue(
                client=self.tasks,
                config=CONFIG,
                already_exists_errors=(AlreadyExistsForTest,),
                not_found_errors=(NotFoundForTest,),
            ),
            warehouse=BigQueryAnalyticsWarehouse(
                query_runner=self.queries,
                config=CONFIG,
            ),
        )
        return AnalyticsService(
            project_id="test-project",
            environment="production",
            keyring=self.keyring,
            backend=backend,
            clock=lambda: NOW,
            event_id_factory=lambda _now: event_id,
            nonce_factory=lambda: f"nonce-for-{event_id}",
            task_audience=TASK_AUDIENCE,
            task_service_account=TASK_IDENTITY,
        )

    def outbox_document(self, event_key: str) -> dict[str, object]:
        document = self.firestore.collection(OUTBOX_COLLECTION).document(event_key).document
        assert document is not None
        return document

    def live_documents(self, collection: str) -> dict[str, dict[str, object]]:
        return {
            document_id: reference.document
            for document_id, reference in self.firestore.collection(collection).references.items()
            if reference.document is not None
        }


def issue_profile(service: AnalyticsService):
    return service.issue_profile_confirmed(subject_uid=SUBJECT_UID)


def receipt_request(issued) -> AnalyticsReceiptRequest:
    return AnalyticsReceiptRequest(
        schemaVersion="analytics-v1.0.0",
        eventId=issued.event_id,
        actionReceipt=issued.action_receipt,
    )


def test_production_occurrence_and_task_survive_backend_reconstruction() -> None:
    rig = ProductionRig()
    first_service = rig.make_service()
    issued = issue_profile(first_service)

    document = rig.outbox_document(issued.row.event_key)
    assert document["deliveryState"] == "queued"
    assert document["attemptCount"] == 0
    assert document["sealedDeliveryPayload"]
    assert len(rig.tasks.tasks) == 1
    assert not hasattr(first_service.backend, "outbox")
    assert not hasattr(first_service.backend, "tasks")

    reconstructed = rig.make_service()
    resumed = reconstructed.resume(
        subject_uid=SUBJECT_UID,
        request=receipt_request(issued),
    )

    assert resumed.status == "queued"
    assert len(rig.tasks.tasks) == 1
    assert len(rig.live_documents(OUTBOX_COLLECTION)) == 1


def test_two_backend_instances_get_only_one_active_firestore_lease() -> None:
    rig = ProductionRig()
    issued = issue_profile(rig.make_service())
    first_worker = rig.make_service()
    second_worker = rig.make_service()
    lease_acquired = threading.Event()
    release_write = threading.Event()

    def pause_after_lease() -> None:
        lease_acquired.set()
        assert release_write.wait(timeout=2)

    with ThreadPoolExecutor(max_workers=1) as pool:
        first_result = pool.submit(
            first_worker.deliver,
            issued.task.delivery_handle,
            claims=_task_claims(),
            before_warehouse_write=pause_after_lease,
        )
        assert lease_acquired.wait(timeout=2)
        try:
            with pytest.raises(AnalyticsDeliveryRetry, match="lease"):
                second_worker.deliver(
                    issued.task.delivery_handle,
                    claims=_task_claims(),
                )
            assert [entry for entry in rig.log if entry == "bigquery:merge"] == []
        finally:
            release_write.set()
        assert first_result.result(timeout=2).status == "written"

    assert [entry for entry in rig.log if entry == "bigquery:merge"] == ["bigquery:merge"]
    document = rig.outbox_document(issued.row.event_key)
    assert document["deliveryState"] == "written"
    assert document["attemptCount"] == 1


def test_retry_and_terminal_states_persist_across_backend_reconstruction() -> None:
    rig = ProductionRig()
    issued = issue_profile(rig.make_service())
    rig.queries.fail_writes = 1

    with pytest.raises(AnalyticsDeliveryRetry):
        rig.make_service().deliver(
            issued.task.delivery_handle,
            claims=_task_claims(),
        )

    retry_document = rig.outbox_document(issued.row.event_key)
    assert retry_document["deliveryState"] == "queued"
    assert retry_document["attemptCount"] == 1
    assert retry_document["leaseAcquiredAt"] is None
    assert retry_document["leaseExpiresAt"] is None
    assert retry_document["expiresAt"] is None
    assert retry_document["sealedDeliveryPayload"]

    result = rig.make_service().deliver(
        issued.task.delivery_handle,
        claims=_task_claims(),
    )

    assert result.status == "written"
    terminal_document = rig.outbox_document(issued.row.event_key)
    assert terminal_document["deliveryState"] == "written"
    assert terminal_document["attemptCount"] == 2
    assert terminal_document["leaseAcquiredAt"] is None
    assert terminal_document["leaseExpiresAt"] is None
    assert terminal_document["sealedDeliveryPayload"] is None
    assert terminal_document["expiresAt"] == NOW + timedelta(days=7)


def test_deletion_fence_is_worker_derivable_but_not_joinable() -> None:
    keyring = ProductionRig().keyring

    for version, subject_key in keyring.subject_keys_for_deletion(SUBJECT_UID).items():
        request_fence_key = keyring.deletion_fence_key(SUBJECT_UID, version=version)
        worker_fence_key = keyring.deletion_fence_key_for_subject_key(
            subject_key,
            version=version,
        )

        assert request_fence_key == worker_fence_key
        assert request_fence_key != subject_key
        assert SUBJECT_UID not in request_fence_key
        assert subject_key not in request_fence_key


def test_named_cloud_task_cancellation_is_idempotent() -> None:
    log: list[str] = []
    client = FakeTasksClient(log)
    queue = CloudTasksAnalyticsQueue(
        client=client,
        config=CONFIG,
        already_exists_errors=(AlreadyExistsForTest,),
        not_found_errors=(NotFoundForTest,),
    )
    task_name = "analytics-fixed-task-name"
    full_name = f"{queue.parent}/tasks/{task_name}"
    client.tasks[full_name] = {"name": full_name}

    queue.cancel(task_name)
    queue.cancel(task_name)

    assert client.tasks == {}
    assert log == [f"tasks:delete:{full_name}"]


def test_subject_deletion_fences_then_cancels_then_deletes_every_linkable_record() -> None:
    rig = ProductionRig()
    first = issue_profile(rig.make_service(event_id=EVENT_ID_1))
    second = issue_profile(rig.make_service(event_id=EVENT_ID_2))
    rig.make_service().deliver(first.task.delivery_handle, claims=_task_claims())
    _add_subject_and_project_counters(rig)
    rig.log.clear()

    rig.make_service().delete_subject(SUBJECT_UID)

    subject_keys = set(rig.keyring.subject_keys_for_deletion(SUBJECT_UID).values())
    expected_fences = {
        rig.keyring.deletion_fence_key_for_subject_key(subject_key, version=version)
        for version, subject_key in rig.keyring.subject_keys_for_deletion(SUBJECT_UID).items()
    }
    fence_documents = _fence_documents(rig, expected_fences)
    assert set(fence_documents) == expected_fences
    for document in fence_documents.values():
        assert document["expiresAt"] == NOW + timedelta(days=97)
        _assert_contains_no_subject_material(document, subject_keys)

    assert rig.live_documents(OUTBOX_COLLECTION) == {}
    counters = rig.live_documents("runtime_quota_counters_v1")
    assert set(counters) == {"project-counter"}
    delete_calls = [
        call for call in rig.queries.calls if str(call["query"]).lstrip().startswith("DELETE")
    ]
    assert delete_calls[-1]["parameters"] == {"subject_keys": sorted(subject_keys)}
    assert rig.tasks.tasks == {}

    first_fence = min(
        index for index, entry in enumerate(rig.log) if _log_mentions_any(entry, expected_fences)
    )
    first_cancel = next(index for index, entry in enumerate(rig.log) if entry.startswith("tasks:delete:"))
    warehouse_delete = rig.log.index("bigquery:delete")
    first_outbox_delete = next(
        index
        for index, entry in enumerate(rig.log)
        if entry.startswith(f"firestore:delete:{OUTBOX_COLLECTION}/")
    )
    assert first_fence < first_cancel < warehouse_delete < first_outbox_delete
    assert second.task.name not in json.dumps(rig.tasks.tasks)


def test_in_flight_worker_checks_persisted_fence_before_bigquery_write() -> None:
    rig = ProductionRig()
    issued = issue_profile(rig.make_service())
    deleting_service = rig.make_service()
    rig.log.clear()

    result = rig.make_service().deliver(
        issued.task.delivery_handle,
        claims=_task_claims(),
        before_warehouse_write=lambda: deleting_service.delete_subject(SUBJECT_UID),
    )

    assert result.status == "discarded"
    assert "bigquery:delete" in rig.log
    assert "bigquery:merge" not in rig.log
    assert rig.live_documents(OUTBOX_COLLECTION) == {}


def test_failed_bigquery_deletion_keeps_fence_and_only_non_content_retry_state() -> None:
    rig = ProductionRig()
    issued = issue_profile(rig.make_service())
    rig.queries.fail_deletes = 1
    rig.log.clear()

    with pytest.raises(AnalyticsDeliveryRetry):
        rig.make_service().delete_subject(SUBJECT_UID)

    subject_keys_by_version = rig.keyring.subject_keys_for_deletion(SUBJECT_UID)
    subject_keys = set(subject_keys_by_version.values())
    expected_fences = {
        rig.keyring.deletion_fence_key_for_subject_key(subject_key, version=version)
        for version, subject_key in subject_keys_by_version.items()
    }
    fence_documents = _fence_documents(rig, expected_fences)
    assert set(fence_documents) == expected_fences
    for document in fence_documents.values():
        assert document["deletionState"] == "retry_pending"
        _assert_contains_no_subject_material(document, subject_keys)
    assert issued.row.event_key in rig.live_documents(OUTBOX_COLLECTION)
    assert not any(
        entry.startswith(f"firestore:delete:{OUTBOX_COLLECTION}/") for entry in rig.log
    )

    rig.make_service().delete_subject(SUBJECT_UID)
    assert rig.live_documents(OUTBOX_COLLECTION) == {}


def _task_claims() -> TaskAuthClaims:
    return TaskAuthClaims(
        issuer="https://accounts.google.com",
        audience=TASK_AUDIENCE,
        serviceAccount=TASK_IDENTITY,
    )


def _add_subject_and_project_counters(rig: ProductionRig) -> None:
    collection = rig.firestore.collection("runtime_quota_counters_v1")
    collection.document("subject-counter").document = {
        "scopeKind": "subject",
        "scopeHash": hashlib.sha256(SUBJECT_UID.encode()).hexdigest(),
    }
    collection.document("project-counter").document = {
        "scopeKind": "project",
        "scopeHash": hashlib.sha256(b"test-project").hexdigest(),
    }


def _fence_documents(
    rig: ProductionRig,
    expected_fences: set[str],
) -> dict[str, dict[str, object]]:
    return {
        document_id: document
        for collection_name in rig.firestore.collections
        if collection_name != OUTBOX_COLLECTION
        for document_id, document in rig.live_documents(collection_name).items()
        if document_id in expected_fences
    }


def _assert_contains_no_subject_material(
    document: dict[str, object],
    subject_keys: set[str],
) -> None:
    serialized = json.dumps(document, default=str)
    assert SUBJECT_UID not in serialized
    for subject_key in subject_keys:
        assert subject_key not in serialized


def _log_mentions_any(entry: str, values: set[str]) -> bool:
    return any(value in entry for value in values)
