from dataclasses import replace

import pytest

from scripts.sc710_configured_evidence import (
    EVIDENCE_FIXTURE_SUBJECT_UID,
    MAXIMUM_BYTES_BILLED,
    ConfiguredEvidenceConfig,
    EvidencePhase,
    build_parser,
    confirmation_phrase,
    execute_phase,
)

PROJECT_ID = "patchamomma-2026-505415"
LOCATION = "asia-south1"
QUEUE_PATH = (
    "projects/patchamomma-2026-505415/locations/asia-south1/queues/analytics-delivery"
)
TASK_IDENTITY = (
    "sakhi-task-delivery@patchamomma-2026-505415.iam.gserviceaccount.com"
)
TASK_AUDIENCE = "https://sc710-evidence.invalid/internal/v1/analytics/deliver"


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
        maximum_bytes_billed=20 * 1024 * 1024,
    )


class FakeOperations:
    def __init__(
        self,
        *,
        queue_state: str = "PAUSED",
        failure: str | None = None,
        result: object = None,
    ) -> None:
        self.queue_state_value = queue_state
        self.failure = failure
        self.result = result
        self.calls: list[tuple[str, object]] = []

    def queue_state(self, *, queue_path: str) -> str:
        self.calls.append(("queue_state", queue_path))
        return self.queue_state_value

    def preflight(self, *, config: ConfiguredEvidenceConfig, fixture_subject_uid: str):
        return self._run("preflight", config, fixture_subject_uid)

    def forged_rejection(
        self,
        *,
        config: ConfiguredEvidenceConfig,
        fixture_subject_uid: str,
    ):
        return self._run("forged-rejection", config, fixture_subject_uid)

    def create_signed_fixture(
        self,
        *,
        config: ConfiguredEvidenceConfig,
        fixture_subject_uid: str,
    ):
        return self._run("create-signed-fixture", config, fixture_subject_uid)

    def transient_worker_failure(
        self,
        *,
        config: ConfiguredEvidenceConfig,
        fixture_subject_uid: str,
    ):
        return self._run("transient-worker-failure", config, fixture_subject_uid)

    def deliver_once(
        self,
        *,
        config: ConfiguredEvidenceConfig,
        fixture_subject_uid: str,
    ):
        return self._run("deliver-once", config, fixture_subject_uid)

    def verify_one_row(
        self,
        *,
        config: ConfiguredEvidenceConfig,
        fixture_subject_uid: str,
    ):
        return self._run("verify-one-row", config, fixture_subject_uid)

    def delete_fixture(
        self,
        *,
        config: ConfiguredEvidenceConfig,
        fixture_subject_uid: str,
    ):
        return self._run("delete-fixture", config, fixture_subject_uid)

    def verify_deleted(
        self,
        *,
        config: ConfiguredEvidenceConfig,
        fixture_subject_uid: str,
    ):
        return self._run("verify-deleted", config, fixture_subject_uid)

    def _run(
        self,
        name: str,
        config: ConfiguredEvidenceConfig,
        fixture_subject_uid: str,
    ):
        self.calls.append(
            (
                name,
                {
                    "config": config,
                    "fixture_subject_uid": fixture_subject_uid,
                },
            )
        )
        if self.failure is not None:
            raise RuntimeError(self.failure)
        return self.result


def test_phase_order_keeps_each_query_or_mutation_separately_approval_gated() -> None:
    assert [phase.value for phase in EvidencePhase] == [
        "preflight",
        "forged-rejection",
        "create-signed-fixture",
        "transient-worker-failure",
        "deliver-once",
        "verify-one-row",
        "delete-fixture",
        "verify-deleted",
    ]


@pytest.mark.parametrize(
    ("field", "unsafe_value"),
    (
        ("project_id", "different-project"),
        ("location", "us-central1"),
        ("firestore_database_id", "evidence-db"),
        ("private_dataset_id", "public_analytics"),
        ("analytics_table_id", "different_table"),
        ("queue_id", "different-queue"),
        ("task_service_account", "owner@example.com"),
        ("task_audience", "https://example.com/receiver"),
        ("hmac_secret_name", "different-secret"),
        ("hmac_secret_versions", ("latest",)),
        ("current_hmac_secret_version", "2"),
        ("maximum_bytes_billed", 20 * 1024 * 1024 + 1),
    ),
)
def test_exact_free_trial_resource_and_cost_boundary_is_fail_closed(
    field: str,
    unsafe_value: object,
) -> None:
    config = replace(evidence_config(), **{field: unsafe_value})
    operations = FakeOperations()

    with pytest.raises(ValueError, match="SC-710 configured evidence boundary"):
        execute_phase(
            config=config,
            phase=EvidencePhase.PREFLIGHT,
            operations=operations,
            input_fn=lambda _prompt: confirmation_phrase(EvidencePhase.PREFLIGHT, PROJECT_ID),
            output_fn=lambda _message: None,
        )

    assert operations.calls == []


def test_wrong_confirmation_causes_zero_cloud_client_calls() -> None:
    operations = FakeOperations()
    output: list[str] = []

    succeeded = execute_phase(
        config=evidence_config(),
        phase=EvidencePhase.CREATE_SIGNED_FIXTURE,
        operations=operations,
        input_fn=lambda _prompt: "no",
        output_fn=output.append,
    )

    assert succeeded is False
    assert operations.calls == []
    assert output == ["SC-710 create-signed-fixture: CANCELLED"]


def test_every_phase_refuses_to_run_unless_the_delivery_queue_is_paused() -> None:
    operations = FakeOperations(queue_state="RUNNING")
    output: list[str] = []

    succeeded = execute_phase(
        config=evidence_config(),
        phase=EvidencePhase.TRANSIENT_WORKER_FAILURE,
        operations=operations,
        input_fn=lambda _prompt: confirmation_phrase(
            EvidencePhase.TRANSIENT_WORKER_FAILURE,
            PROJECT_ID,
        ),
        output_fn=output.append,
    )

    assert succeeded is False
    assert operations.calls == [("queue_state", QUEUE_PATH)]
    assert output == ["SC-710 transient-worker-failure: BLOCKED (queue must be PAUSED)"]


@pytest.mark.parametrize("phase", tuple(EvidencePhase))
def test_each_confirmed_phase_invokes_only_its_named_bounded_operation(
    phase: EvidencePhase,
) -> None:
    operations = FakeOperations(result={"aggregateCount": 1})
    output: list[str] = []

    succeeded = execute_phase(
        config=evidence_config(),
        phase=phase,
        operations=operations,
        input_fn=lambda _prompt: confirmation_phrase(phase, PROJECT_ID),
        output_fn=output.append,
    )

    assert succeeded is True
    assert operations.calls == [
        ("queue_state", QUEUE_PATH),
        (
            phase.value,
            {
                "config": evidence_config(),
                "fixture_subject_uid": EVIDENCE_FIXTURE_SUBJECT_UID,
            },
        ),
    ]
    assert output == [f"SC-710 {phase.value}: PASS"]


def test_sensitive_operation_results_are_never_rendered() -> None:
    canaries = {
        "secretValue": "secret-value-canary",
        "actionReceipt": "receipt-canary",
        "deliveryHandle": "handle-canary",
        "eventId": "event-id-canary",
        "eventKey": "event-key-canary",
        "subjectKey": "subject-key-canary",
        "row": "row-canary",
        "token": "token-canary",
        "learner": "learner-canary",
    }
    output: list[str] = []

    succeeded = execute_phase(
        config=evidence_config(),
        phase=EvidencePhase.VERIFY_ONE_ROW,
        operations=FakeOperations(result=canaries),
        input_fn=lambda _prompt: confirmation_phrase(EvidencePhase.VERIFY_ONE_ROW, PROJECT_ID),
        output_fn=output.append,
    )

    assert succeeded is True
    rendered = "\n".join(output)
    assert rendered == "SC-710 verify-one-row: PASS"
    assert all(str(value) not in rendered for value in canaries.values())


def test_unexpected_operation_errors_fail_closed_without_printing_error_content() -> None:
    output: list[str] = []

    succeeded = execute_phase(
        config=evidence_config(),
        phase=EvidencePhase.DELETE_FIXTURE,
        operations=FakeOperations(failure="secret-value-canary handle-canary learner-canary"),
        input_fn=lambda _prompt: confirmation_phrase(EvidencePhase.DELETE_FIXTURE, PROJECT_ID),
        output_fn=output.append,
    )

    assert succeeded is False
    assert output == ["SC-710 delete-fixture: FAIL"]


def test_cli_requires_one_explicit_phase_and_project() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "--phase",
            "verify-deleted",
            "--project",
            PROJECT_ID,
        ]
    )

    assert args.phase == EvidencePhase.VERIFY_DELETED
    assert args.project == PROJECT_ID


def test_fixture_and_query_limits_are_fixed_non_identifying_values() -> None:
    assert EVIDENCE_FIXTURE_SUBJECT_UID == "sc710-configured-evidence-fixture-v1"
    assert MAXIMUM_BYTES_BILLED == 20 * 1024 * 1024
    assert "@" not in EVIDENCE_FIXTURE_SUBJECT_UID
    assert "gmail" not in EVIDENCE_FIXTURE_SUBJECT_UID
