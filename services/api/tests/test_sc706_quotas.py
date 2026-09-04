from datetime import UTC, datetime, timedelta

import pytest

from app.quotas import (
    InMemoryQuotaCounterStore,
    QuotaExceeded,
    QuotaService,
    QuotaStoreUnavailable,
)


class MutableClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class UnavailableStore:
    def reserve(self, *_args: object, **_kwargs: object) -> None:
        raise QuotaStoreUnavailable("counter backend unavailable")


def test_general_protected_limit_is_60_requests_per_rolling_minute() -> None:
    clock = MutableClock(datetime(2026, 9, 2, 8, 0, tzinfo=UTC))
    quotas = QuotaService(InMemoryQuotaCounterStore(), clock=clock)

    for _ in range(60):
        quotas.reserve_general_request("subject-a")
    clock.now += timedelta(seconds=59)
    with pytest.raises(QuotaExceeded) as denied:
        quotas.reserve_general_request("subject-a")
    assert denied.value.code == "protected_api_quota_exceeded"
    assert denied.value.retry_after == 1

    clock.now += timedelta(seconds=1)
    quotas.reserve_general_request("subject-a")


def test_recommendation_subject_day_resets_at_india_midnight() -> None:
    clock = MutableClock(datetime(2026, 9, 2, 18, 29, 59, tzinfo=UTC))
    quotas = QuotaService(InMemoryQuotaCounterStore(), clock=clock)

    for _ in range(20):
        quotas.reserve_recommendation("subject-a")
    with pytest.raises(QuotaExceeded) as denied:
        quotas.reserve_recommendation("subject-a")
    assert denied.value.code == "recommendation_quota_exceeded"
    assert denied.value.retry_after == 1

    clock.now += timedelta(seconds=1)
    quotas.reserve_recommendation("subject-a")


def test_recommendation_project_day_limit_is_shared_across_subjects() -> None:
    quotas = QuotaService(
        InMemoryQuotaCounterStore(),
        clock=lambda: datetime(2026, 9, 2, 8, 0, tzinfo=UTC),
    )

    for index in range(500):
        quotas.reserve_recommendation(f"subject-{index}")
    with pytest.raises(QuotaExceeded) as denied:
        quotas.reserve_recommendation("subject-501")
    assert denied.value.code == "recommendation_quota_exceeded"


def test_analytics_identical_retry_does_not_consume_another_daily_unit() -> None:
    quotas = QuotaService(
        InMemoryQuotaCounterStore(),
        clock=lambda: datetime(2026, 9, 2, 8, 0, tzinfo=UTC),
    )

    quotas.reserve_analytics_event("subject-a", "event-1")
    quotas.reserve_analytics_event("subject-a", "event-1")
    for index in range(2, 21):
        quotas.reserve_analytics_event("subject-a", f"event-{index}")
    with pytest.raises(QuotaExceeded) as denied:
        quotas.reserve_analytics_event("subject-a", "event-21")
    assert denied.value.code == "analytics_quota_exceeded"


def test_gemini_subject_limit_is_three_workflows_per_rolling_24_hours() -> None:
    clock = MutableClock(datetime(2026, 9, 2, 8, 0, tzinfo=UTC))
    quotas = QuotaService(InMemoryQuotaCounterStore(), clock=clock)

    for _ in range(3):
        quotas.reserve_gemini_workflow("subject-a", project_daily_allowance=20)
    clock.now += timedelta(hours=23, minutes=59, seconds=59)
    with pytest.raises(QuotaExceeded) as denied:
        quotas.reserve_gemini_workflow("subject-a", project_daily_allowance=20)
    assert denied.value.code == "gemini_quota_exceeded"
    assert denied.value.retry_after == 1

    clock.now += timedelta(seconds=1)
    quotas.reserve_gemini_workflow("subject-a", project_daily_allowance=20)


def test_gemini_project_allowance_is_atomic_and_never_above_immutable_20() -> None:
    quotas = QuotaService(
        InMemoryQuotaCounterStore(),
        clock=lambda: datetime(2026, 9, 2, 8, 0, tzinfo=UTC),
    )

    for index in range(20):
        quotas.reserve_gemini_workflow(
            f"subject-{index}",
            project_daily_allowance=20,
        )
    with pytest.raises(QuotaExceeded):
        quotas.reserve_gemini_workflow("subject-21", project_daily_allowance=20)
    with pytest.raises(ValueError, match="immutable deployment maximum"):
        quotas.reserve_gemini_workflow("subject-22", project_daily_allowance=21)


def test_counter_state_is_shared_by_multiple_service_instances() -> None:
    store = InMemoryQuotaCounterStore()
    now = lambda: datetime(2026, 9, 2, 8, 0, tzinfo=UTC)
    first_instance = QuotaService(store, clock=now)
    second_instance = QuotaService(store, clock=now)

    for _ in range(3):
        first_instance.reserve_gemini_workflow("subject-a", project_daily_allowance=20)
    with pytest.raises(QuotaExceeded):
        second_instance.reserve_gemini_workflow("subject-a", project_daily_allowance=20)


def test_unavailable_persistent_counter_fails_closed() -> None:
    quotas = QuotaService(UnavailableStore())

    with pytest.raises(QuotaStoreUnavailable):
        quotas.reserve_gemini_workflow("subject-a", project_daily_allowance=20)
