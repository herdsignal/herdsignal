import hashlib
import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

from scheduler import herd_scheduler


class SchedulerRunHistoryTest(unittest.TestCase):
    def test_duplicate_execution_is_skipped_before_run_history_is_created(self) -> None:
        with (
            patch.object(
                herd_scheduler.SchedulerRunLock,
                "try_acquire",
                return_value=None,
            ),
            patch.object(herd_scheduler, "_start_scheduler_run") as start,
        ):
            result = herd_scheduler.run_herd_job(trigger_type="MANUAL")

        self.assertEqual(result["status"], "DUPLICATE_SKIPPED")
        start.assert_not_called()

    def test_run_history_records_partial_failure(self) -> None:
        herd_result = {"score": 50.0, "stage": "Calm"}

        with (
            patch.object(
                herd_scheduler.SchedulerRunLock,
                "try_acquire",
                return_value=MagicMock(),
            ),
            patch.object(herd_scheduler, "_start_scheduler_run", return_value=7),
            patch.object(herd_scheduler, "_record_scheduler_universe"),
            patch.object(herd_scheduler, "_fetch_tier1_tickers", return_value=["AAPL", "SNDK"]),
            patch.object(herd_scheduler, "collect", return_value=object()),
            patch.object(herd_scheduler, "validate_operational_price_frame"),
            patch.object(herd_scheduler, "run", return_value=herd_result),
            patch.object(
                herd_scheduler,
                "save_herd_result",
                side_effect=lambda ticker, *_: ticker == "AAPL",
            ),
            patch.object(
                herd_scheduler,
                "_snapshot_all_portfolios",
                return_value={"requested": [], "saved": [], "errors": []},
            ),
            patch.object(
                herd_scheduler,
                "_build_and_write_observation",
                return_value={
                    "records": {"SPY": {"asOfDate": "2026-07-24"}}
                },
            ) as build_observation,
            patch.object(herd_scheduler, "_finish_scheduler_run") as finish,
            patch.object(herd_scheduler, "_notify_scheduler_result") as notify,
        ):
            result = herd_scheduler.run_herd_job(trigger_type="MANUAL")

        self.assertEqual(result, {
            "status": "PARTIAL_FAILURE",
            "total": 2,
            "success": ["AAPL"],
            "failed": ["SNDK"],
            "skipped": [],
            "observation": "SKIPPED_INCOMPLETE_INPUT",
            "universeSha256": hashlib.sha256(b"AAPL\nSNDK\n").hexdigest(),
        })
        build_observation.assert_not_called()
        finish.assert_called_once_with(
            7,
            "PARTIAL_FAILURE",
            total_count=2,
            success_count=1,
            failed_tickers=["SNDK"],
            skipped_tickers=[],
            publish_status="SKIPPED_INCOMPLETE_INPUT",
            observation_count=None,
            error_message=None,
        )
        notify.assert_called_once_with(result)

    def test_portfolio_snapshots_cover_each_user_and_isolate_failures(self) -> None:
        with (
            patch.object(
                herd_scheduler,
                "_fetch_portfolio_user_ids",
                return_value=["local", "user-2"],
            ),
            patch.object(
                herd_scheduler,
                "calculate_portfolio_value",
                side_effect=[
                    {"stocks": [{"ticker": "SPY"}], "total_value": 100.0},
                    RuntimeError("price missing"),
                ],
            ) as calculate,
        ):
            result = herd_scheduler._snapshot_all_portfolios()

        self.assertEqual(result["requested"], ["local", "user-2"])
        self.assertEqual(result["saved"], ["local"])
        self.assertEqual(result["errors"], ["user-2: price missing"])
        self.assertEqual(
            [call.args[0] for call in calculate.call_args_list],
            ["local", "user-2"],
        )

    def test_run_history_records_failure_when_ticker_lookup_fails(self) -> None:
        with (
            patch.object(
                herd_scheduler.SchedulerRunLock,
                "try_acquire",
                return_value=MagicMock(),
            ),
            patch.object(herd_scheduler, "_start_scheduler_run", return_value=9),
            patch.object(herd_scheduler, "_fetch_tier1_tickers", side_effect=RuntimeError("db unavailable")),
            patch.object(herd_scheduler, "_finish_scheduler_run") as finish,
            patch.object(herd_scheduler, "_notify_scheduler_result") as notify,
        ):
            result = herd_scheduler.run_herd_job(trigger_type="SCHEDULED")

        self.assertEqual(result["status"], "FAILED")
        finish.assert_called_once_with(9, "FAILED", error_message="db unavailable")
        notify.assert_called_once_with(result)
