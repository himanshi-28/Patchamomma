from types import SimpleNamespace

import pytest

from scripts.sc710_configured_evidence import (
    EVIDENCE_FIXTURE_SUBJECT_UID,
    GoogleConfiguredEvidenceOperations,
    build_google_configured_evidence_operations,
    confirmation_phrase,
    run_cli,
)

PROJECT_ID = "patchamomma-2026-505415"
QUEUE_PATH = (
    "projects/patchamomma-2026-505415/locations/asia-south1/"
    "queues/analytics-delivery"
)


class RecordingOperations:
    def __init__(self, *, queue_state: str = "PAUSED") -> None:
        self.queue_state_value = queue_state
        self.calls: list[tuple[str, object]] = []

    def queue_state(self, *, queue_path: str) -> str:
        self.calls.append(("queue_state", queue_path))
        return self.queue_state_value

    def __getattr__(self, name: str):
        def operation(*, config: object, fixture_subject_uid: str) -> None:
            self.calls.append(
                (
                    name,
                    {
                        "config": config,
                        "fixture_subject_uid": fixture_subject_uid,
                    },
                )
            )

        return operation


def test_cli_cancellation_constructs_no_google_operations_or_clients() -> None:
    factory_calls: list[object] = []
    output: list[str] = []

    exit_code = run_cli(
        ["--phase", "preflight", "--project", PROJECT_ID],
        input_fn=lambda _prompt: "no",
        output_fn=output.append,
        operations_factory=lambda config: factory_calls.append(config),
    )

    assert exit_code == 1
    assert factory_calls == []
    assert output == ["SC-710 preflight: CANCELLED"]


@pytest.mark.parametrize(
    ("phase", "method_name"),
    (
        ("preflight", "preflight"),
        ("forged-rejection", "forged_rejection"),
        ("create-signed-fixture", "create_signed_fixture"),
        ("transient-worker-failure", "transient_worker_failure"),
        ("deliver-once", "deliver_once"),
        ("verify-one-row", "verify_one_row"),
        ("delete-fixture", "delete_fixture"),
        ("verify-deleted", "verify_deleted"),
    ),
)
def test_confirmed_cli_invocation_runs_only_one_selected_phase(
    phase: str,
    method_name: str,
) -> None:
    operations = RecordingOperations()
    factory_calls: list[object] = []
    output: list[str] = []

    def operations_factory(config: object) -> RecordingOperations:
        factory_calls.append(config)
        return operations

    exit_code = run_cli(
        ["--phase", phase, "--project", PROJECT_ID],
        input_fn=lambda _prompt: confirmation_phrase(phase, PROJECT_ID),
        output_fn=output.append,
        operations_factory=operations_factory,
    )

    assert exit_code == 0
    assert len(factory_calls) == 1
    assert operations.calls == [
        ("queue_state", QUEUE_PATH),
        (
            method_name,
            {
                "config": factory_calls[0],
                "fixture_subject_uid": EVIDENCE_FIXTURE_SUBJECT_UID,
            },
        ),
    ]
    assert output == [f"SC-710 {phase}: PASS"]


def test_cli_does_not_construct_operations_when_exact_resource_boundary_is_wrong() -> None:
    factory_calls: list[object] = []

    with pytest.raises(ValueError, match="SC-710 configured evidence boundary"):
        run_cli(
            ["--phase", "preflight", "--project", "different-project"],
            input_fn=lambda _prompt: confirmation_phrase("preflight", "different-project"),
            output_fn=lambda _message: None,
            operations_factory=lambda config: factory_calls.append(config),
        )

    assert factory_calls == []


def test_cli_suppresses_google_factory_and_client_error_content() -> None:
    canary = "adc-secret-client-error-canary"
    output: list[str] = []

    def failing_factory(_config: object) -> object:
        raise RuntimeError(canary)

    exit_code = run_cli(
        ["--phase", "verify-one-row", "--project", PROJECT_ID],
        input_fn=lambda _prompt: confirmation_phrase("verify-one-row", PROJECT_ID),
        output_fn=output.append,
        operations_factory=failing_factory,
    )

    assert exit_code == 1
    assert output == ["SC-710 verify-one-row: FAIL"]
    assert canary not in "\n".join(output)


def test_google_composition_uses_only_locked_resources_and_injected_sdk_loader() -> None:
    gateway = object()
    query_runner = object()
    tasks_client = SimpleNamespace()
    sdk_clients = SimpleNamespace(tasks=tasks_client)
    analytics_service = SimpleNamespace(
        backend=SimpleNamespace(
            outbox_store=SimpleNamespace(gateway=gateway),
            warehouse=SimpleNamespace(query_runner=query_runner),
        )
    )
    loader_calls: list[object] = []
    builder_calls: list[tuple[object, object]] = []

    def sdk_loader(config: object) -> object:
        loader_calls.append(config)
        return sdk_clients

    def analytics_builder(settings: object, *, clients: object) -> object:
        builder_calls.append((settings, clients))
        return SimpleNamespace(analytics_service=analytics_service)

    operations = build_google_configured_evidence_operations(
        project_id=PROJECT_ID,
        sdk_loader=sdk_loader,
        analytics_builder=analytics_builder,
        full_task_view="FULL",
    )

    assert isinstance(operations, GoogleConfiguredEvidenceOperations)
    assert len(loader_calls) == 1
    production_config = loader_calls[0]
    assert production_config.model_dump(by_alias=True) == {
        "projectId": PROJECT_ID,
        "firestoreDatabaseId": "(default)",
        "location": "asia-south1",
        "privateDatasetId": "sakhi_analytics",
        "analyticsTableId": "checkpoint_events_v1",
        "reportingDatasetId": "sakhi_reporting",
        "reportingViewId": "checkpoint_metrics_v1",
        "queueId": "analytics-delivery",
        "taskServiceAccount": (
            "sakhi-task-delivery@patchamomma-2026-505415.iam.gserviceaccount.com"
        ),
        "taskAudience": (
            "https://sc710-evidence.invalid/internal/v1/analytics/deliver"
        ),
        "hmacSecretName": "sakhi-analytics-hmac-key",
        "hmacSecretVersions": ["1"],
        "currentHmacSecretVersion": "1",
    }
    assert len(builder_calls) == 1
    settings, clients = builder_calls[0]
    assert clients is sdk_clients
    assert settings.app_env == "production"
    assert settings.adapter_mode == "production"
    assert settings.firebase_project_id == PROJECT_ID
    assert settings.analytics_hmac_secret_versions == ["1"]
    assert settings.analytics_current_hmac_secret_version == "1"
    assert operations.firestore_gateway is gateway
    assert operations.tasks_client is tasks_client
    assert operations.query_runner is query_runner
    assert operations.full_task_view == "FULL"
    assert operations.task_claims.model_dump(by_alias=True) == {
        "issuer": "https://accounts.google.com",
        "audience": "https://sc710-evidence.invalid/internal/v1/analytics/deliver",
        "serviceAccount": (
            "sakhi-task-delivery@patchamomma-2026-505415.iam.gserviceaccount.com"
        ),
    }


def test_cli_has_no_queue_state_mutation_capability() -> None:
    operations = RecordingOperations(queue_state="RUNNING")
    output: list[str] = []

    exit_code = run_cli(
        ["--phase", "create-signed-fixture", "--project", PROJECT_ID],
        input_fn=lambda _prompt: confirmation_phrase(
            "create-signed-fixture",
            PROJECT_ID,
        ),
        output_fn=output.append,
        operations_factory=lambda _config: operations,
    )

    assert exit_code == 1
    assert operations.calls == [("queue_state", QUEUE_PATH)]
    assert output == [
        "SC-710 create-signed-fixture: BLOCKED (queue must be PAUSED)"
    ]
