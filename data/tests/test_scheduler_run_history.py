import hashlib
import unittest
from unittest.mock import ANY, MagicMock
from unittest.mock import patch

from scheduler import herd_scheduler


class SchedulerRunHistoryTest(unittest.TestCase):
    def test_daily_job_matures_outcomes_and_refreshes_readiness_reports(
        self,
    ) -> None:
        frame = object()
        prospective = {
            "maturity": {
                "status": "SUCCESS",
                "created": 3,
                "pending": 17,
            },
            "outcomeCollectionFailed": [],
        }
        with (
            patch.object(herd_scheduler, "_start_scheduler_run", return_value=12),
            patch.object(herd_scheduler, "_record_scheduler_universe"),
            patch.object(herd_scheduler, "_fetch_tier1_tickers", return_value=["AAPL"]),
            patch.object(herd_scheduler, "load_operational_identity_starts", return_value={}),
            patch.object(
                herd_scheduler,
                "collect_ticker_frames_with_retry",
                return_value=({"AAPL": frame}, [], []),
            ),
            patch.object(
                herd_scheduler,
                "_build_and_write_daily_observation",
                return_value={"records": {"AAPL": {}}},
            ),
            patch.object(
                herd_scheduler,
                "_mature_prospective_evidence",
                return_value=prospective,
            ) as mature,
            patch.object(
                herd_scheduler,
                "refresh_operational_reports",
                return_value={"reports": ["a", "b", "c"]},
            ) as refresh_reports,
            patch.object(
                herd_scheduler,
                "_snapshot_all_portfolios",
                return_value={"requested": [], "saved": [], "errors": []},
            ),
            patch.object(herd_scheduler, "_finish_scheduler_run") as finish,
            patch.object(herd_scheduler, "_notify_scheduler_result"),
        ):
            result = herd_scheduler._run_daily_observation_job_unlocked("MANUAL")

        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["prospectiveEvidence"], prospective)
        self.assertEqual(
            result["phases"]["PROSPECTIVE_OUTCOMES"],
            {
                "status": "SUCCESS",
                "count": 3,
                "detail": "대기 17, 수집 실패 0",
            },
        )
        self.assertEqual(
            result["phases"]["READINESS_REPORTS"],
            {"status": "SUCCESS", "count": 3},
        )
        mature.assert_called_once_with({"AAPL": frame})
        refresh_reports.assert_called_once_with()
        finish.assert_called_once_with(
            12,
            "SUCCESS",
            total_count=1,
            success_count=1,
            failed_tickers=[],
            publish_status="SUCCESS",
            observation_count=1,
            phase_results=result["phases"],
            error_message=None,
            job_name=herd_scheduler._DAILY_JOB_NAME,
        )

    def test_daily_outcome_maturity_keeps_removed_archived_tickers(self) -> None:
        with (
            patch.object(
                herd_scheduler,
                "_complete_prospective_outcome_frames",
                return_value=({"AAPL": "current", "REMOVED": "history"}, ["MISS"]),
            ) as complete,
            patch.object(
                herd_scheduler,
                "mature_outcomes",
                return_value={"status": "SUCCESS", "created": 1, "pending": 2},
            ) as mature,
        ):
            result = herd_scheduler._mature_prospective_evidence(
                {"AAPL": "current"}
            )

        self.assertEqual(result["outcomeCollectionFailed"], ["MISS"])
        self.assertEqual(result["maturity"]["created"], 1)
        complete.assert_called_once_with({"AAPL": "current"})
        mature.assert_called_once_with({"AAPL": "current", "REMOVED": "history"})

    def test_outcome_tracking_collects_archived_ticker_removed_from_current_scope(
        self,
    ) -> None:
        old_frame = object()
        with (
            patch.object(
                herd_scheduler,
                "archived_tickers",
                return_value={"AAPL", "REMOVED"},
            ),
            patch.object(
                herd_scheduler,
                "collect_ticker_frames",
                return_value=({"REMOVED": old_frame}, []),
            ) as collect_missing,
        ):
            frames, failed = herd_scheduler._complete_prospective_outcome_frames(
                {"AAPL": "current"}
            )

        self.assertEqual(frames, {"AAPL": "current", "REMOVED": old_frame})
        self.assertEqual(failed, [])
        collect_missing.assert_called_once_with(
            ["REMOVED"],
            herd_scheduler.collect,
            validate=herd_scheduler.validate_operational_price_frame,
        )

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
            patch.object(
                herd_scheduler,
                "_fetch_operational_tickers",
                return_value=["AAPL"],
            ),
            patch.object(
                herd_scheduler,
                "collect_ticker_frames_with_retry",
                return_value=({"AAPL": object()}, ["SNDK"], []),
            ),
            patch.object(
                herd_scheduler,
                "load_operational_identity_starts",
                return_value={},
            ),
            patch.object(
                herd_scheduler,
                "apply_operational_identity_window",
                side_effect=lambda ticker, frame, **_: frame,
            ),
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
            patch.object(
                herd_scheduler,
                "_build_and_write_daily_observation",
                return_value={
                    "records": {"SPY": {"asOfDate": "2026-07-28"}}
                },
            ) as build_daily_observation,
            patch.object(
                herd_scheduler,
                "_complete_prospective_outcome_frames",
                return_value=({"AAPL": object()}, []),
            ) as complete_outcomes,
            patch.object(
                herd_scheduler,
                "_record_prospective_evidence",
                return_value={
                    "archive": {
                        "status": "SUCCESS",
                        "recordCount": 1,
                    },
                    "maturity": {
                        "status": "SUCCESS",
                        "created": 0,
                        "pending": 0,
                    },
                },
            ) as record_prospective,
            patch.object(herd_scheduler, "_finish_scheduler_run") as finish,
            patch.object(herd_scheduler, "_notify_scheduler_result") as notify,
        ):
            result = herd_scheduler.run_herd_job(trigger_type="MANUAL")

        self.assertEqual({key: value for key, value in result.items() if key != "phases"}, {
            "status": "PARTIAL_FAILURE",
            "total": 2,
            "success": ["AAPL"],
            "failed": ["SNDK"],
            "skipped": [],
            "observation": "SUCCESS",
            "universeSha256": hashlib.sha256(b"AAPL\nSNDK\n").hexdigest(),
            "prospectiveEvidence": {
                "archive": {
                    "status": "SUCCESS",
                    "recordCount": 1,
                },
                "maturity": {
                    "status": "SUCCESS",
                    "created": 0,
                    "pending": 0,
                },
                "outcomeCollectionFailed": [],
            },
        })
        build_observation.assert_called_once_with({"AAPL": ANY}, ["AAPL"])
        build_daily_observation.assert_called_once_with({"AAPL": ANY}, ["AAPL"])
        complete_outcomes.assert_called_once_with({"AAPL": ANY})
        record_prospective.assert_called_once_with(ANY, {"AAPL": ANY})
        finish.assert_called_once_with(
            7,
            "PARTIAL_FAILURE",
            total_count=2,
            success_count=1,
            failed_tickers=["SNDK"],
            skipped_tickers=[],
            publish_status="SUCCESS",
            observation_count=1,
            error_message=None,
            phase_results=result["phases"],
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
        finish.assert_called_once_with(
            9,
            "FAILED",
            phase_results={
                "UNIVERSE": {"status": "FAILED", "detail": "db unavailable"}
            },
            error_message="db unavailable",
        )
        notify.assert_called_once_with(result)
