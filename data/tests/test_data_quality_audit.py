import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.data_quality_audit import audit_price_frame, build_data_quality_report


def _valid_prices(rows: int = 1_000) -> pd.DataFrame:
    dates = pd.date_range(end="2026-07-17", periods=rows, freq="B")
    close = pd.Series(range(100, 100 + rows), dtype=float)
    return pd.DataFrame({
        "Date": dates,
        "Open": close,
        "High": close + 1,
        "Low": close - 1,
        "Close": close,
        "Volume": 1_000,
    })


class DataQualityAuditTest(unittest.TestCase):
    def test_valid_price_frame_passes(self):
        report = audit_price_frame(_valid_prices(), as_of=date(2026, 7, 19))

        self.assertTrue(report["passed"])
        self.assertEqual(report["staleness_days"], 2)

    def test_duplicate_invalid_ohlc_and_stale_data_fail(self):
        prices = _valid_prices()
        prices.loc[1, "Date"] = prices.loc[0, "Date"]
        prices.loc[2, "High"] = prices.loc[2, "Low"] - 1

        report = audit_price_frame(prices, as_of=date(2026, 8, 19))

        self.assertFalse(report["passed"])
        self.assertFalse(report["checks"]["unique_dates"])
        self.assertFalse(report["checks"]["valid_ohlc_bounds"])
        self.assertFalse(report["checks"]["fresh"])

    def test_floating_point_ohlc_noise_is_tolerated(self):
        prices = _valid_prices()
        prices.loc[2, "Low"] = prices.loc[2, "Close"] + 1e-14

        report = audit_price_frame(prices, as_of=date(2026, 7, 19))

        self.assertTrue(report["checks"]["valid_ohlc_bounds"])

    def test_empty_universe_and_missing_pit_data_block_full_readiness(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "universe.csv"
            path.write_text(
                "ticker,start_date,end_date,sector,exit_reason,source\n",
                encoding="utf-8",
            )
            report = build_data_quality_report(
                {"SPY": {"passed": True}},
                universe_history_path=path,
                fixed_tickers=["SPY"],
            )

        self.assertTrue(report["readiness"]["price_only_research_ready"])
        self.assertFalse(report["readiness"]["survivorship_safe_validation_ready"])
        self.assertEqual(report["readiness"]["status"], "PARTIAL_PRICE_ONLY")
        self.assertEqual(
            report["corporate_actions"]["status"],
            "ADJUSTED_ONLY_NOT_AUDITABLE",
        )


if __name__ == "__main__":
    unittest.main()
