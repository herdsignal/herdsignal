import unittest
from unittest.mock import patch

from scheduler import herd_scheduler


class SchedulerRunHistoryTest(unittest.TestCase):
    def test_run_history_records_partial_failure(self) -> None:
        herd_result = {"score": 50.0, "stage": "Calm"}

        with (
            patch.object(herd_scheduler, "_start_scheduler_run", return_value=7),
            patch.object(herd_scheduler, "_fetch_tier1_tickers", return_value=["AAPL", "SNDK"]),
            patch.object(herd_scheduler, "collect", return_value=object()),
            patch.object(herd_scheduler, "run", return_value=herd_result),
            patch.object(
                herd_scheduler,
                "save_herd_result",
                side_effect=lambda ticker, *_: ticker == "AAPL",
            ),
            patch.object(herd_scheduler, "calculate_portfolio_value", return_value={"stocks": []}),
            patch.object(herd_scheduler, "_finish_scheduler_run") as finish,
        ):
            result = herd_scheduler.run_herd_job(trigger_type="MANUAL")

        self.assertEqual(result, {
            "status": "PARTIAL_FAILURE",
            "total": 2,
            "success": ["AAPL"],
            "failed": ["SNDK"],
        })
        finish.assert_called_once_with(
            7,
            "PARTIAL_FAILURE",
            total_count=2,
            success_count=1,
            failed_tickers=["SNDK"],
            error_message=None,
        )

    def test_run_history_records_failure_when_ticker_lookup_fails(self) -> None:
        with (
            patch.object(herd_scheduler, "_start_scheduler_run", return_value=9),
            patch.object(herd_scheduler, "_fetch_tier1_tickers", side_effect=RuntimeError("db unavailable")),
            patch.object(herd_scheduler, "_finish_scheduler_run") as finish,
        ):
            result = herd_scheduler.run_herd_job(trigger_type="SCHEDULED")

        self.assertEqual(result["status"], "FAILED")
        finish.assert_called_once_with(9, "FAILED", error_message="db unavailable")
