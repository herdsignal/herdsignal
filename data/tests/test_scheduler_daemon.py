from datetime import UTC, datetime
from unittest.mock import MagicMock

from scheduler.daemon import run_with_single_retry, startup_catchup_due


def test_scheduled_failure_retries_once_with_explicit_trigger() -> None:
    job = MagicMock(side_effect=[
        {"status": "PARTIAL_FAILURE"},
        {"status": "SUCCESS"},
    ])

    result = run_with_single_retry(job)

    assert result["status"] == "SUCCESS"
    assert job.call_count == 2
    job.assert_any_call(trigger_type="SCHEDULED")
    job.assert_any_call(trigger_type="AUTOMATIC_RETRY")


def test_success_does_not_retry() -> None:
    job = MagicMock(return_value={"status": "SUCCESS"})

    assert run_with_single_retry(job)["status"] == "SUCCESS"
    job.assert_called_once_with(trigger_type="SCHEDULED")


def test_duplicate_skip_does_not_retry() -> None:
    job = MagicMock(return_value={"status": "DUPLICATE_SKIPPED"})

    assert run_with_single_retry(job)["status"] == "DUPLICATE_SKIPPED"
    job.assert_called_once()


def test_unhandled_exception_retries_once() -> None:
    job = MagicMock(side_effect=[RuntimeError("network"), {"status": "SUCCESS"}])

    assert run_with_single_retry(job)["status"] == "SUCCESS"
    assert job.call_count == 2


def test_startup_catchup_is_due_after_schedule_without_today_success() -> None:
    now = datetime(2026, 7, 27, 22, 0, tzinfo=UTC)  # 18:00 ET
    old_success = datetime(2026, 7, 26, 22, 0, tzinfo=UTC)

    assert startup_catchup_due(
        old_success,
        now=now,
        hour_et=16,
        minute_et=30,
    )


def test_startup_catchup_is_not_due_before_schedule_or_after_success() -> None:
    before = datetime(2026, 7, 27, 19, 0, tzinfo=UTC)  # 15:00 ET
    after = datetime(2026, 7, 27, 22, 0, tzinfo=UTC)
    today_success = datetime(2026, 7, 27, 21, 0, tzinfo=UTC)

    assert not startup_catchup_due(
        None,
        now=before,
        hour_et=16,
        minute_et=30,
    )
    assert not startup_catchup_due(
        today_success,
        now=after,
        hour_et=16,
        minute_et=30,
    )
