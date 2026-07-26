from unittest.mock import MagicMock

from scheduler.daemon import run_with_single_retry


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
