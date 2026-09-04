import tomllib
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app import analytics_google
from app.analytics import (
    AnalyticsConflict,
    AnalyticsKeyring,
    AnalyticsService,
    InMemoryAnalyticsBackend,
    StaticTaskTokenVerifier,
    TaskAuthClaims,
)
from app.config import Settings
from app.cost_controls import CostControlState
from app.main import create_app
from app.quotas import InMemoryQuotaCounterStore, QuotaService

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPOSITORY_ROOT / "services" / "api"
NOW = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)
TASK_AUDIENCE = "https://api.example.test/internal/v1/analytics/deliver"
TASK_IDENTITY = "sakhi-task-delivery@test-project.iam.gserviceaccount.com"


def production_settings() -> Settings:
    return Settings(
        app_env="production",
        adapter_mode="production",
        firebase_project_id="test-project",
        firebase_app_id="web-app",
        firestore_database_id="(default)",
        analytics_location="asia-south1",
        analytics_private_dataset_id="sakhi_analytics",
        analytics_table_id="checkpoint_events_v1",
        analytics_reporting_dataset_id="sakhi_reporting",
        analytics_reporting_view_id="checkpoint_metrics_v1",
        analytics_queue_id="analytics-delivery",
        analytics_task_service_account=TASK_IDENTITY,
        analytics_task_audience=TASK_AUDIENCE,
        analytics_hmac_secret_name="sakhi-analytics-hmac-key",
        analytics_hmac_secret_versions=["7", "8"],
        analytics_current_hmac_secret_version="8",
    )


def test_direct_google_sdk_dependencies_are_declared_for_reproducible_deployments() -> None:
    project = tomllib.loads((API_ROOT / "pyproject.toml").read_text())
    dependencies = {
        value.split(">=", 1)[0].split("<", 1)[0] for value in project["project"]["dependencies"]
    }

    assert {
        "google-auth",
        "google-cloud-bigquery",
        "google-cloud-firestore",
        "google-cloud-secret-manager",
        "google-cloud-tasks",
    }.issubset(dependencies)


def test_cloud_run_template_binds_every_approved_analytics_resource_without_a_secret() -> None:
    manifest = (API_ROOT / "cloud-run.service.yaml.tmpl").read_text()
    required_bindings = {
        "SAKHI_FIRESTORE_DATABASE_ID": "(default)",
        "SAKHI_ANALYTICS_LOCATION": "asia-south1",
        "SAKHI_ANALYTICS_PRIVATE_DATASET_ID": "sakhi_analytics",
        "SAKHI_ANALYTICS_TABLE_ID": "checkpoint_events_v1",
        "SAKHI_ANALYTICS_REPORTING_DATASET_ID": "sakhi_reporting",
        "SAKHI_ANALYTICS_REPORTING_VIEW_ID": "checkpoint_metrics_v1",
        "SAKHI_ANALYTICS_QUEUE_ID": "analytics-delivery",
        "SAKHI_ANALYTICS_TASK_SERVICE_ACCOUNT": (
            "sakhi-task-delivery@patchamomma-2026-505415.iam.gserviceaccount.com"
        ),
        "SAKHI_ANALYTICS_HMAC_SECRET_NAME": "sakhi-analytics-hmac-key",
    }
    for name, value in required_bindings.items():
        assert f"name: {name}\n              value: {value}" in manifest

    assert "name: SAKHI_ANALYTICS_TASK_AUDIENCE" in manifest
    assert "value: ${ANALYTICS_TASK_AUDIENCE}" in manifest
    assert "name: SAKHI_ANALYTICS_HMAC_SECRET_VERSIONS" in manifest
    assert "name: SAKHI_ANALYTICS_CURRENT_HMAC_SECRET_VERSION" in manifest
    assert "secretKeyRef" not in manifest
    assert "sakhi-analytics-hmac-key/versions/" not in manifest


class FakeQueryJob:
    def __init__(self) -> None:
        self.result_calls = 0

    def result(self) -> list[object]:
        self.result_calls += 1
        return []


class FakeBigQueryClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.job = FakeQueryJob()

    def query(self, query: str, *, job_config: object, location: str) -> FakeQueryJob:
        self.calls.append({"query": query, "job_config": job_config, "location": location})
        return self.job


def test_bigquery_query_runner_builds_typed_parameters_waits_and_enforces_byte_cap() -> None:
    client = FakeBigQueryClient()
    scalar_calls: list[tuple[str, str, object]] = []
    array_calls: list[tuple[str, str, list[str]]] = []

    def scalar(name: str, parameter_type: str, value: object) -> tuple[object, ...]:
        scalar_calls.append((name, parameter_type, value))
        return ("scalar", name, parameter_type, value)

    def array(name: str, parameter_type: str, value: list[str]) -> tuple[object, ...]:
        array_calls.append((name, parameter_type, value))
        return ("array", name, parameter_type, value)

    def job_config(**values: object) -> dict[str, object]:
        return dict(values)

    runner = analytics_google.GoogleBigQueryQueryRunner(
        client=client,
        scalar_parameter_factory=scalar,
        array_parameter_factory=array,
        job_config_factory=job_config,
    )

    runner(
        query="SELECT @event_key",
        parameters={
            "event_key": "opaque-event-key",
            "event_date": "2026-09-02",
            "event_timestamp": "2026-09-02T08:00:00Z",
            "journey_fallback_used": False,
            "result_count": None,
            "subject_keys": ["subject-key-1", "subject-key-2"],
        },
        maximum_bytes_billed=20 * 1024 * 1024,
        location="asia-south1",
    )

    assert scalar_calls == [
        ("event_key", "STRING", "opaque-event-key"),
        ("event_date", "DATE", "2026-09-02"),
        ("event_timestamp", "TIMESTAMP", "2026-09-02T08:00:00Z"),
        ("journey_fallback_used", "BOOL", False),
        ("result_count", "INT64", None),
    ]
    assert array_calls == [("subject_keys", "STRING", ["subject-key-1", "subject-key-2"])]
    assert client.calls == [
        {
            "query": "SELECT @event_key",
            "job_config": {
                "query_parameters": [("scalar", *values) for values in scalar_calls]
                + [("array", *values) for values in array_calls],
                "maximum_bytes_billed": 20 * 1024 * 1024,
                "use_legacy_sql": False,
            },
            "location": "asia-south1",
        }
    ]
    assert client.job.result_calls == 1


class FakeSnapshot:
    def __init__(
        self,
        document_id: str,
        document: dict[str, object] | None,
    ) -> None:
        self.id = document_id
        self.exists = document is not None
        self._document = document

    def to_dict(self) -> dict[str, object] | None:
        return self._document


class FakeDocumentReference:
    def __init__(self, document_id: str) -> None:
        self.id = document_id
        self.document: dict[str, object] | None = None

    def get(self, *, transaction: object) -> FakeSnapshot:
        assert transaction is not None
        return FakeSnapshot(self.id, self.document)


class FakeCollection:
    def __init__(self) -> None:
        self.references: dict[str, FakeDocumentReference] = {}
        self.lookup_snapshots: list[FakeSnapshot] = []
        self.filter: object | None = None
        self.limit_value: int | None = None

    def document(self, document_id: str) -> FakeDocumentReference:
        return self.references.setdefault(document_id, FakeDocumentReference(document_id))

    def where(self, *, filter: object):
        self.filter = filter
        return self

    def limit(self, value: int):
        self.limit_value = value
        return self

    def stream(self) -> list[FakeSnapshot]:
        return self.lookup_snapshots


class FakeTransaction:
    def __init__(self) -> None:
        self.creates: list[tuple[FakeDocumentReference, dict[str, object]]] = []

    def create(
        self,
        reference: FakeDocumentReference,
        document: dict[str, object],
    ) -> None:
        self.creates.append((reference, document))
        reference.document = document


class FakeFirestoreClient:
    def __init__(self) -> None:
        self.collections: dict[str, FakeCollection] = {}
        self.active_transaction = FakeTransaction()

    def collection(self, name: str) -> FakeCollection:
        return self.collections.setdefault(name, FakeCollection())

    def transaction(self) -> FakeTransaction:
        return self.active_transaction


def run_transaction_immediately(function):
    return function


def test_firestore_gateway_creates_atomically_resumes_identical_and_queries_hash_only() -> None:
    client = FakeFirestoreClient()
    field_filters: list[tuple[str, str, object]] = []

    def field_filter(field: str, operator: str, value: object) -> tuple[str, str, object]:
        created = (field, operator, value)
        field_filters.append(created)
        return created

    gateway = analytics_google.GoogleFirestoreAnalyticsGateway(
        client=client,
        transactional=run_transaction_immediately,
        field_filter_factory=field_filter,
    )
    document = {
        "payloadHash": "a" * 64,
        "deliveryHandleHash": "opaque-hash",
        "sealedDeliveryPayload": "ciphertext",
    }

    created = gateway.create_occurrence(
        collection="analytics_outbox_v1",
        document_id="event-key",
        document=document,
    )
    identical = gateway.create_occurrence(
        collection="analytics_outbox_v1",
        document_id="event-key",
        document=document,
    )

    assert created == ("event-key", document)
    assert identical == ("event-key", document)
    assert len(client.active_transaction.creates) == 1

    with pytest.raises(AnalyticsConflict, match="event_id_conflict"):
        gateway.create_occurrence(
            collection="analytics_outbox_v1",
            document_id="event-key",
            document={**document, "payloadHash": "b" * 64},
        )

    collection = client.collection("analytics_outbox_v1")
    collection.lookup_snapshots = [FakeSnapshot("event-key", document)]
    found = gateway.find_by_delivery_handle_hashes(
        collection="analytics_outbox_v1",
        hashes=["old-hash", "current-hash"],
        limit=2,
    )

    assert field_filters == [("deliveryHandleHash", "in", ["old-hash", "current-hash"])]
    assert collection.limit_value == 2
    assert found == [("event-key", document)]


class FakeSecretManagerClient:
    def __init__(self) -> None:
        self.names: list[str] = []

    def access_secret_version(self, *, request: dict[str, str]):
        self.names.append(request["name"])
        version = request["name"].rsplit("/", 1)[-1]
        return SimpleNamespace(payload=SimpleNamespace(data=f"key-{version}".encode()))


def test_production_builder_wires_service_backend_and_task_verifier_without_other_calls() -> None:
    secrets = FakeSecretManagerClient()
    firestore = FakeFirestoreClient()
    tasks = SimpleNamespace(create_task=lambda **_kwargs: None)
    bigquery = FakeBigQueryClient()

    clients = analytics_google.GoogleSdkClients(
        secret_manager=secrets,
        firestore=firestore,
        tasks=tasks,
        bigquery=bigquery,
        verify_google_token=lambda _token, **kwargs: {
            "iss": "https://accounts.google.com",
            "aud": kwargs["audience"],
            "email": TASK_IDENTITY,
            "email_verified": True,
        },
        firestore_transactional=run_transaction_immediately,
        firestore_field_filter_factory=lambda field, operator, value: (
            field,
            operator,
            value,
        ),
        bigquery_scalar_parameter_factory=lambda *values: values,
        bigquery_array_parameter_factory=lambda *values: values,
        bigquery_job_config_factory=lambda **values: values,
        already_exists_errors=(),
    )

    bindings = analytics_google.build_production_analytics(
        production_settings(),
        clients=clients,
    )

    assert isinstance(bindings, analytics_google.ProductionAnalyticsBindings)
    assert bindings.analytics_service.environment == "production"
    assert isinstance(
        bindings.analytics_service.backend,
        analytics_google.GoogleAnalyticsBackend,
    )
    claims = bindings.task_token_verifier.verify("signed-task-token")
    assert claims.service_account == TASK_IDENTITY
    assert secrets.names == [
        "projects/test-project/secrets/sakhi-analytics-hmac-key/versions/7",
        "projects/test-project/secrets/sakhi-analytics-hmac-key/versions/8",
    ]
    assert firestore.collections == {}
    assert tasks.__dict__ == {"create_task": tasks.create_task}
    assert bigquery.calls == []


class AvailableCostControls:
    def read(self) -> CostControlState:
        return CostControlState(
            schemaVersion="cost-controls-v1.0.0",
            geminiProjectDailyAllowance=0,
            maintenanceMode=False,
            updatedAt=NOW,
        )


def test_production_startup_installs_both_analytics_and_google_task_verification() -> None:
    analytics = AnalyticsService(
        project_id="test-project",
        environment="production",
        keyring=AnalyticsKeyring(
            project_id="test-project",
            keys={"8": b"test-key"},
            current_version="8",
        ),
        backend=InMemoryAnalyticsBackend(),
        task_audience=TASK_AUDIENCE,
        task_service_account=TASK_IDENTITY,
    )
    verifier = StaticTaskTokenVerifier(
        {
            "task-token": TaskAuthClaims(
                issuer="https://accounts.google.com",
                audience=TASK_AUDIENCE,
                serviceAccount=TASK_IDENTITY,
            )
        }
    )
    bindings = analytics_google.ProductionAnalyticsBindings(
        analytics_service=analytics,
        task_token_verifier=verifier,
    )

    with patch(
        "app.analytics_google.build_production_analytics",
        return_value=bindings,
    ):
        app = create_app(
            production_settings(),
            cost_control_reader=AvailableCostControls(),
            quota_service=QuotaService(InMemoryQuotaCounterStore()),
        )

    assert app.state.analytics_service is analytics
    assert app.state.task_token_verifier is verifier
