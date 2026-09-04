from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from app.analytics import (
    AnalyticsConflict,
    AnalyticsDeliveryRetry,
    AnalyticsKeyring,
    AnalyticsReceiptRequest,
    AnalyticsService,
    InMemoryAnalyticsBackend,
    TaskAuthClaims,
)

NOW = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)
EVENT_ID = "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d1"
TASK_CLAIMS = TaskAuthClaims(
    issuer="https://accounts.google.com",
    audience="https://api.example.test/internal/v1/analytics/deliver",
    service_account="sakhi-task-delivery@test-project.iam.gserviceaccount.com",
)


def make_service(
    backend: InMemoryAnalyticsBackend | None = None,
) -> tuple[AnalyticsService, InMemoryAnalyticsBackend]:
    resolved_backend = backend or InMemoryAnalyticsBackend()
    service = AnalyticsService(
        project_id="test-project",
        environment="test",
        keyring=AnalyticsKeyring(
            project_id="test-project",
            keys={"8": b"current-test-key"},
            current_version="8",
        ),
        backend=resolved_backend,
        clock=lambda: NOW,
        event_id_factory=lambda _now: EVENT_ID,
        nonce_factory=lambda: "fixed-test-nonce",
        task_audience=TASK_CLAIMS.audience,
        task_service_account=TASK_CLAIMS.service_account,
    )
    return service, resolved_backend


def issue(service: AnalyticsService):
    return service.issue_journey_draft_created(
        subject_uid="firebase-user",
        journey_schema_version="1.0.0",
        generator="deterministic_fixture",
        fallback_used=False,
    )


def receipt_request(issued) -> AnalyticsReceiptRequest:
    return AnalyticsReceiptRequest(
        schemaVersion="analytics-v1.0.0",
        eventId=issued.event_id,
        actionReceipt=issued.action_receipt,
    )


def test_identical_receipt_retry_resumes_one_occurrence_and_one_row() -> None:
    service, backend = make_service()
    issued = issue(service)
    request = receipt_request(issued)

    first = service.resume(subject_uid="firebase-user", request=request)
    service.deliver(issued.task.delivery_handle, claims=TASK_CLAIMS)
    second = service.resume(subject_uid="firebase-user", request=request)

    assert first.status == "queued"
    assert second.status == "written"
    assert second.duplicate is True
    assert len(backend.outbox) == 1
    assert len(backend.warehouse_rows) == 1
    assert backend.enqueue_count == 1


def test_same_event_id_with_changed_signed_payload_conflicts_without_overwrite() -> None:
    service, backend = make_service()
    first = issue(service)
    first_hash = first.row.payload_hash

    service.nonce_factory = lambda: "second-nonce"
    with pytest.raises(AnalyticsConflict, match="event_id_conflict"):
        service.issue_journey_draft_created(
            subject_uid="firebase-user",
            journey_schema_version="1.0.0",
            generator="curated_fallback",
            fallback_used=True,
        )

    assert len(backend.outbox) == 1
    assert next(iter(backend.outbox.values())).payload_hash == first_hash


def test_concurrent_delivery_and_ambiguous_write_retry_still_create_one_row() -> None:
    service, backend = make_service()
    issued = issue(service)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _index: service.deliver(
                    issued.task.delivery_handle,
                    claims=TASK_CLAIMS,
                ),
                range(2),
            )
        )

    assert len(backend.warehouse_rows) == 1
    assert {result.status for result in results} == {"written"}

    next_event_id = "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d2"
    service.event_id_factory = lambda _now: next_event_id
    another = issue(service)
    backend.raise_ambiguous_after_next_insert = True
    with pytest.raises(AnalyticsDeliveryRetry):
        service.deliver(another.task.delivery_handle, claims=TASK_CLAIMS)
    retried = service.deliver(another.task.delivery_handle, claims=TASK_CLAIMS)

    assert retried.status == "written"
    assert len(backend.warehouse_rows) == 2


def test_task_is_durable_named_and_contains_only_an_opaque_handle() -> None:
    service, backend = make_service()
    issued = issue(service)
    task = issued.task

    assert task.name.startswith("analytics-")
    assert task.name not in {issued.event_id, issued.row.event_key}
    assert set(task.body) == {"deliveryHandle"}
    assert task.body["deliveryHandle"] == task.delivery_handle
    assert issued.event_id not in str(task.body)
    assert issued.row.event_key not in str(task.body)
    assert issued.row.subject_key not in str(task.body)
    assert "firebase-user" not in str(task.body)
    assert task.max_attempts == 8
    assert task.max_retry_duration == timedelta(hours=24)
    assert task.min_backoff == timedelta(seconds=10)
    assert task.max_backoff == timedelta(minutes=15)

    record = next(iter(backend.outbox.values()))
    assert record.expires_at is None
    assert record.delivery_handle_hash
    assert record.delivery_handle_hash != task.delivery_handle
    assert record.sealed_delivery_payload
    assert task.delivery_handle not in record.model_dump_json()
    assert issued.event_id not in record.sealed_delivery_payload
    assert not hasattr(backend, "_rows_by_event_key")
    assert set(record.model_dump(by_alias=True, exclude_none=False)) == {
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

    recreated_service, _ = make_service(backend)
    result = recreated_service.deliver(task.delivery_handle, claims=TASK_CLAIMS)
    assert result.status == "written"
    assert len(backend.warehouse_rows) == 1


def test_transient_failure_retries_and_eighth_failure_is_terminal_with_seven_day_ttl() -> None:
    service, backend = make_service()
    issued = issue(service)
    backend.fail_next_writes = 1

    with pytest.raises(AnalyticsDeliveryRetry):
        service.run_task(issued.task.name, claims=TASK_CLAIMS)
    completed = service.run_task(issued.task.name, claims=TASK_CLAIMS)

    assert completed.status == "written"
    record = next(iter(backend.outbox.values()))
    assert record.attempt_count == 2
    assert record.expires_at == NOW + timedelta(days=7)
    assert record.sealed_delivery_payload is None

    service.event_id_factory = lambda _now: "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d2"
    exhausted = issue(service)
    backend.fail_next_writes = 8
    for _attempt in range(7):
        with pytest.raises(AnalyticsDeliveryRetry):
            service.run_task(exhausted.task.name, claims=TASK_CLAIMS)
    terminal = service.run_task(exhausted.task.name, claims=TASK_CLAIMS)

    assert terminal.status == "failed"
    exhausted_record = backend.outbox[exhausted.row.event_key]
    assert exhausted_record.attempt_count == 8
    assert exhausted_record.failure_code == "delivery_retry_exhausted"
    assert exhausted_record.expires_at == NOW + timedelta(days=7)
    assert exhausted_record.sealed_delivery_payload is None


def test_deletion_fence_stops_in_flight_write_and_removes_every_linkable_record() -> None:
    service, backend = make_service()
    first = issue(service)
    service.event_id_factory = lambda _now: "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d2"
    second = issue(service)
    service.deliver(first.task.delivery_handle, claims=TASK_CLAIMS)
    backend.linkable_counter_records[first.row.subject_key] = {"count": 1}

    result = service.deliver(
        second.task.delivery_handle,
        claims=TASK_CLAIMS,
        before_warehouse_write=lambda: service.delete_subject("firebase-user"),
    )

    assert result.status == "discarded"
    assert backend.warehouse_rows == {}
    assert backend.outbox == {}
    assert backend.tasks == {}
    assert backend.linkable_counter_records == {}
    assert len(backend.deletion_fences) == 1
    fence = next(iter(backend.deletion_fences.values()))
    assert fence.expires_at == NOW + timedelta(days=97)
    assert "firebase-user" not in fence.model_dump_json()
    assert first.row.subject_key not in fence.model_dump_json()


def test_deterministic_backend_makes_zero_network_or_paid_calls() -> None:
    service, backend = make_service()
    issued = issue(service)
    service.resume(subject_uid="firebase-user", request=receipt_request(issued))
    service.deliver(issued.task.delivery_handle, claims=TASK_CLAIMS)
    service.delete_subject("firebase-user")

    assert backend.network_call_count == 0
    assert backend.paid_call_count == 0
