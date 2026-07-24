import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from scheduler.run_history import SchedulerRunRecorder
from scheduler.ticker_job import execute_tickers


class SchedulerComponentsTest(unittest.TestCase):
    def test_ticker_execution_isolates_individual_failure(self):
        collect = MagicMock(side_effect=lambda ticker: ticker)
        calculate = MagicMock(side_effect=lambda ticker, frame: {"score": 50, "stage": "Calm"})
        save = MagicMock(side_effect=lambda ticker, result, frame: ticker != "BAD")
        success, failed = execute_tickers(["AAPL", "BAD", "NVDA"], collect, calculate, save)
        self.assertEqual(success, ["AAPL", "NVDA"])
        self.assertEqual(failed, ["BAD"])

    def test_ticker_execution_exposes_only_successfully_saved_frames(self):
        collected = []
        success, failed = execute_tickers(
            ["AAPL", "BAD"],
            collect=lambda ticker: f"frame:{ticker}",
            calculate=lambda ticker, frame: {"score": 50, "stage": "Calm"},
            save=lambda ticker, result, frame: ticker != "BAD",
            on_success=lambda ticker, frame: collected.append((ticker, frame)),
        )
        self.assertEqual(success, ["AAPL"])
        self.assertEqual(failed, ["BAD"])
        self.assertEqual(collected, [("AAPL", "frame:AAPL")])

    def test_run_recorder_truncates_error_and_serializes_failures(self):
        row = SimpleNamespace()
        session = MagicMock()
        session.get.return_value = row
        context = MagicMock()
        context.__enter__.return_value = session
        recorder = SchedulerRunRecorder(lambda: context, "JOB")
        recorder.finish(3, "PARTIAL_FAILURE", 2, 1, ["BAD"], "x" * 2100)
        self.assertEqual(row.failed_tickers, '["BAD"]')
        self.assertEqual(len(row.error_message), 2000)
        session.commit.assert_called_once()

    def test_missing_run_id_is_noop(self):
        factory = MagicMock()
        SchedulerRunRecorder(factory, "JOB").finish(None, "FAILED")
        factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
