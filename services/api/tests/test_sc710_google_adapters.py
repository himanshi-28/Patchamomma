import json
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from app.analytics import (
    AnalyticsKeyring,
    AnalyticsRow,
    AnalyticsUnavailable,
    DeliveryTask,
    OutboxRecord,
    TaskAuthorizationError,
)
from app.analytics_google import (
    BigQueryAnalyticsWarehouse,
    CloudTasksAnalyticsQueue,
    FirestoreAnalyticsOutboxStore,
    GoogleTaskTokenVerifier,
    ProductionAnalyticsConfig,
    SecretManagerAnalyticsKeyLoader,
)

CONFIG = ProductionAnalyticsConfig(
    projectId="test-project",
    firestoreDatabaseId="(default)",
    location="asia-south1",
    privateDatasetId="sakhi_analytics",
    analyticsTableId="checkpoint_events_v1",
    reportingDatasetId="sakhi_reporting",
    reportingViewId="checkpoint_metrics_v1",
    queueId="analytics-delivery",
    taskServiceAccount="sakhi-task-delivery@test-project.iam.gserviceaccount.com",
    taskAudience="https://api.example.test/internal/v1/analytics/deliver",
    hmacSecretName="sakhi-analytics-hmac-key",
    hmacSecretVersions=["7", "8"],
    currentHmacSecretVersion="8",
)


def analytics_row() -> AnalyticsRow:
    return AnalyticsRow(
        event_date=date(2026, 9, 2),
        event_timestamp=datetime(2026, 9, 2, 8, 0, tzinfo=UTC),
        event_name="profile_confirmed",
        event_id="01a06121-cc00-7b41-8aa4-9ce5f2f6e8d1",
        event_key="event-key-value",
        payload_hash="a" * 64,
        subject_key="subject-key-value",
        subject_key_version="8",
        environment="production",
    )


def analytics_keyring() -> AnalyticsKeyring:
    return AnalyticsKeyring(
        project_id="test-project",
        keys={
            "7": b"older-test-key-material-32-byte",
            "8": b"newer-test-key-material-32-byte",
        },
        current_version="8",
    )


def outbox_record() -> OutboxRecord:
    return OutboxRecord(
        payloadHash="a" * 64,
        subjectKey="subject-key-value",
        subjectKeyVersion="8",
        deliveryHandleHash="delivery-handle-hash",
        sealedDeliveryPayload="v1.8.nonce.ciphertext",
        deliveryState="queued",
        taskName="analytics-task-name",
    )


class FakeSecretManagerClient:
    def __init__(self) -> None:
        self.names: list[str] = []

    def access_secret_version(self, *, request: dict[str, str]):
        self.names.append(request["name"])
        version = request["name"].rsplit("/", 1)[-1]
        return SimpleNamespace(payload=SimpleNamespace(data=f"secret-{version}".encode()))


def test_secret_loader_resolves_only_explicit_versions_and_returns_rotating_keyring() -> None:
    client = FakeSecretManagerClient()
    keyring = SecretManagerAnalyticsKeyLoader(client=client, config=CONFIG).load()

    assert client.names == [
        "projects/test-project/secrets/sakhi-analytics-hmac-key/versions/7",
        "projects/test-project/secrets/sakhi-analytics-hmac-key/versions/8",
    ]
    assert keyring.project_id == "test-project"
    assert keyring.current_version == "8"
    assert keyring.keys == {"7": b"secret-7", "8": b"secret-8"}


def test_secret_loader_fails_closed_when_a_configured_version_is_empty() -> None:
    client = FakeSecretManagerClient()
    client.access_secret_version = lambda **_kwargs: SimpleNamespace(
        payload=SimpleNamespace(data=b"")
    )

    with pytest.raises(AnalyticsUnavailable, match="analytics_configuration_required"):
        SecretManagerAnalyticsKeyLoader(client=client, config=CONFIG).load()


class AlreadyExistsForTest(Exception):
    pass


class FakeTasksClient:
    def __init__(self, *, duplicate: bool = False) -> None:
        self.duplicate = duplicate
        self.requests: list[dict[str, object]] = []

    def create_task(self, *, request: dict[str, object]) -> None:
        self.requests.append(request)
        if self.duplicate:
            raise AlreadyExistsForTest


def delivery_task() -> DeliveryTask:
    return DeliveryTask(
        name="analytics-fixed-task-name",
        deliveryHandle="opaque-random-handle",
    )


@pytest.mark.parametrize("duplicate", (False, True))
def test_cloud_tasks_enqueue_has_exact_region_identity_and_opaque_body(
    duplicate: bool,
) -> None:
    client = FakeTasksClient(duplicate=duplicate)
    queue = CloudTasksAnalyticsQueue(
        client=client,
        config=CONFIG,
        already_exists_errors=(AlreadyExistsForTest,),
    )

    queue.enqueue(delivery_task())

    request = client.requests[0]
    assert request["parent"] == (
        "projects/test-project/locations/asia-south1/queues/analytics-delivery"
    )
    task = request["task"]
    assert task["name"].endswith("/tasks/analytics-fixed-task-name")
    http_request = task["http_request"]
    assert http_request["url"] == CONFIG.task_audience
    assert http_request["http_method"] == "POST"
    assert json.loads(http_request["body"]) == {"deliveryHandle": "opaque-random-handle"}
    assert http_request["oidc_token"] == {
        "service_account_email": CONFIG.task_service_account,
        "audience": CONFIG.task_audience,
    }
    serialized = json.dumps(
        request,
        default=lambda value: value.decode() if isinstance(value, bytes) else str(value),
    )
    assert "sealedDeliveryPayload" not in serialized
    assert "event-key-value" not in serialized
    assert "subject-key-value" not in serialized


def test_google_oidc_verifier_accepts_only_the_locked_issuer_audience_and_identity() -> None:
    calls: list[tuple[str, str]] = []

    def verify(token: str, *, audience: str) -> dict[str, object]:
        calls.append((token, audience))
        return {
            "iss": "https://accounts.google.com",
            "aud": audience,
            "email": CONFIG.task_service_account,
            "email_verified": True,
        }

    verifier = GoogleTaskTokenVerifier(
        verify_google_token=verify,
        audience=CONFIG.task_audience,
        service_account=CONFIG.task_service_account,
    )

    claims = verifier.verify("signed-google-token")

    assert calls == [("signed-google-token", CONFIG.task_audience)]
    assert claims.issuer == "https://accounts.google.com"
    assert claims.audience == CONFIG.task_audience
    assert claims.service_account == CONFIG.task_service_account


@pytest.mark.parametrize(
    ("claim", "value"),
    (
        ("iss", "https://issuer.example.test"),
        ("aud", "https://api.example.test/wrong"),
        ("email", "different@test-project.iam.gserviceaccount.com"),
        ("email_verified", False),
    ),
)
def test_google_oidc_verifier_rejects_every_wrong_task_claim(
    claim: str,
    value: object,
) -> None:
    valid: dict[str, object] = {
        "iss": "https://accounts.google.com",
        "aud": CONFIG.task_audience,
        "email": CONFIG.task_service_account,
        "email_verified": True,
    }
    valid[claim] = value
    verifier = GoogleTaskTokenVerifier(
        verify_google_token=lambda _token, **_kwargs: valid,
        audience=CONFIG.task_audience,
        service_account=CONFIG.task_service_account,
    )

    with pytest.raises(TaskAuthorizationError, match="Task authentication required"):
        verifier.verify("invalid-google-token")


class FakeOutboxLookup:
    def __init__(self, records: list[tuple[str, dict[str, object]]]) -> None:
        self.records = records
        self.collection_names: list[str] = []
        self.lookups: list[list[str]] = []

    def create_occurrence(
        self,
        *,
        collection: str,
        document_id: str,
        document: dict[str, object],
    ) -> tuple[str, dict[str, object]]:
        self.collection_names.append(collection)
        return document_id, document

    def find_by_delivery_handle_hashes(
        self,
        *,
        collection: str,
        hashes: list[str],
        limit: int,
    ) -> list[tuple[str, dict[str, object]]]:
        self.collection_names.append(collection)
        self.lookups.append(hashes)
        assert limit == 2
        return self.records


def test_firestore_outbox_stores_only_the_approved_durable_fields() -> None:
    gateway = FakeOutboxLookup([])
    store = FirestoreAnalyticsOutboxStore(
        gateway=gateway,
        keyring=analytics_keyring(),
    )

    _event_key, document = store.create_occurrence(
        event_key="event-key-value",
        record=outbox_record(),
    )

    assert gateway.collection_names == ["analytics_outbox_v1"]
    assert set(document) == {
        "payloadHash",
        "subjectKey",
        "subjectKeyVersion",
        "deliveryHandleHash",
        "sealedDeliveryPayload",
        "deliveryState",
        "leaseAcquiredAt",
        "leaseExpiresAt",
        "taskName",
        "attemptCount",
        "failureCode",
        "expiresAt",
    }
    serialized = json.dumps(document)
    assert "event-key-value" not in serialized
    assert "opaque-random-handle" not in serialized


def test_firestore_outbox_hashes_handle_under_active_versions_and_requires_one_match() -> None:
    record = outbox_record().model_dump(by_alias=True, mode="json")
    gateway = FakeOutboxLookup([("event-key-value", record)])
    keys = analytics_keyring()
    store = FirestoreAnalyticsOutboxStore(gateway=gateway, keyring=keys)

    event_key, found = store.occurrence_for_handle("opaque-random-handle")

    assert gateway.lookups == [
        [
            keys.delivery_handle_hash("opaque-random-handle", version="7"),
            keys.delivery_handle_hash("opaque-random-handle", version="8"),
        ]
    ]
    assert event_key == "event-key-value"
    assert found.delivery_handle_hash == "delivery-handle-hash"

    gateway.records = []
    with pytest.raises(AnalyticsUnavailable, match="Unknown analytics delivery handle"):
        store.occurrence_for_handle("missing-handle")


class FakeQueryRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def __call__(self, **request: object) -> list[dict[str, object]]:
        self.calls.append(request)
        return []


def test_bigquery_write_is_parameterized_idempotent_partition_bounded_and_cost_capped() -> None:
    runner = FakeQueryRunner()
    warehouse = BigQueryAnalyticsWarehouse(query_runner=runner, config=CONFIG)

    warehouse.write_row(analytics_row())

    call = runner.calls[0]
    query = str(call["query"])
    assert "MERGE `test-project.sakhi_analytics.checkpoint_events_v1`" in query
    assert "FROM (SELECT 1)" in query
    assert "WHERE NOT EXISTS (" in query
    assert "ON FALSE" in query
    assert "event_date" in query
    assert "90 DAY" in query
    assert query.count("event_date = @event_date") == 2
    assert "event_key" in query
    assert "payload_hash" in query
    assert call["maximum_bytes_billed"] == 20 * 1024 * 1024
    assert call["location"] == "asia-south1"
    assert call["parameters"]["event_key"] == "event-key-value"
    assert call["parameters"]["payload_hash"] == "a" * 64
    assert "event-key-value" not in query
    assert "subject-key-value" not in query
    assert "insertAll" not in query


def test_bigquery_deletion_uses_subject_parameters_partition_window_and_same_cost_cap() -> None:
    runner = FakeQueryRunner()
    warehouse = BigQueryAnalyticsWarehouse(query_runner=runner, config=CONFIG)

    warehouse.delete_subject_keys({"subject-key-1", "subject-key-2"})

    call = runner.calls[0]
    query = str(call["query"])
    assert "DELETE FROM `test-project.sakhi_analytics.checkpoint_events_v1`" in query
    assert "event_date" in query
    assert "90 DAY" in query
    assert call["parameters"] == {"subject_keys": ["subject-key-1", "subject-key-2"]}
    assert call["maximum_bytes_billed"] == 20 * 1024 * 1024
    assert "subject-key-1" not in query
