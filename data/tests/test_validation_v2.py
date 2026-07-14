import tempfile
import unittest
from pathlib import Path

import pandas as pd

from herd.validation_v2 import ExecutionConfig, InvestorConfig, apply_point_in_time_sector, build_folds, fold_masks, point_in_time_sector_multiplier, run_realistic_strategy, summarize, write_report


class ValidationV2Test(unittest.TestCase):
    def test_csv_report_excludes_nested_detail(self):
        with tempfile.TemporaryDirectory() as directory:
            _, csv_path = write_report(
                Path(directory), {}, [{
                    "ticker": "SPY", "v61_capture": 100, "v61_mdd_improvement": 1,
                    "v61_return": 2, "fixed_return": 1, "detail": {"events": [1]},
                }], [],
            )
            columns = pd.read_csv(csv_path).columns.tolist()
        self.assertIn("ticker", columns)
        self.assertIn("v61_return", columns)
        self.assertNotIn("detail", columns)

    @staticmethod
    def _hold(_score, _trend, _previous, _days):
        return "HOLD", 0

    def test_executes_signal_on_next_open_with_costs(self):
        dates = pd.date_range("2020-01-01", periods=4, freq="B")
        prices = pd.DataFrame({"Open": [100, 110, 120, 130], "Close": [105, 115, 125, 135]}, index=dates)
        herd = pd.Series([80, 80, 50, 50], index=dates)
        trend = pd.DataFrame({"trend_quality": 50, "ma200_deviation": 50}, index=dates)

        def decide(score, _trend, _previous, _days):
            return ("SELL", 0.5) if score >= 75 else ("HOLD", 0)

        result = run_realistic_strategy("TEST", prices, herd, trend, decide, ExecutionConfig(cooldown_days=20))
        self.assertEqual(result.trades[0].signal_date, "2020-01-01")
        self.assertEqual(result.trades[0].execution_date, "2020-01-02")
        self.assertGreater(result.total_cost, 0)

    def test_builds_time_ordered_folds(self):
        index = pd.date_range("2016-01-01", "2025-12-31", freq="ME")
        anchored = build_folds(index, "anchored")
        rolling = build_folds(index, "rolling")
        self.assertEqual(anchored[0]["train_start"], 2016)
        self.assertEqual(rolling[-1]["train_start"], 2021)
        self.assertLess(anchored[0]["train_end"], anchored[0]["test_start"])

    def test_fold_masks_apply_oos_embargo(self):
        index = pd.date_range("2020-01-01", "2021-12-31", freq="B")
        fold = {"train_start": 2020, "train_end": 2020, "test_start": 2021, "test_end": 2021}
        train, test = fold_masks(index, fold, embargo_days=20)
        self.assertEqual(int(train.sum()), len(index[index.year == 2020]))
        self.assertEqual(int(test.sum()), len(index[index.year == 2021]) - 20)
        self.assertGreater(test[test].index.min(), index[index.year == 2021][19])

    def test_fold_masks_reject_negative_embargo(self):
        with self.assertRaises(ValueError):
            fold_masks(pd.date_range("2020-01-01", periods=2), {
                "train_start": 2019, "train_end": 2019, "test_start": 2020, "test_end": 2020,
            }, embargo_days=-1)

    def test_summary_uses_median_and_improvement_rate(self):
        rows = [
            {"ticker": "A", "v61_capture": 80, "v61_mdd_improvement": 5, "v61_return": 20, "fixed_return": 10},
            {"ticker": "B", "v61_capture": 1000, "v61_mdd_improvement": 7, "v61_return": 5, "fixed_return": 10},
            {"ticker": "C", "v61_capture": 60, "v61_mdd_improvement": 1, "v61_return": 12, "fixed_return": 10},
        ]
        result = summarize(rows)
        self.assertEqual(result["capture_median"], 80)
        self.assertAlmostEqual(result["improvement_rate"], 66.6666666667)

    def test_sector_multiplier_uses_only_past_window(self):
        dates = pd.date_range("2020-01-01", periods=100, freq="B")
        stock = pd.Series(range(100, 200), index=dates, dtype=float)
        sector = pd.Series([100 + i * 0.5 for i in range(100)], index=dates, dtype=float)
        multiplier = point_in_time_sector_multiplier(stock, sector, days=90)
        self.assertEqual(multiplier.iloc[89], 1.0)
        self.assertLess(multiplier.iloc[99], 1.0)
        adjusted = apply_point_in_time_sector(pd.Series(50.0, index=dates), multiplier)
        self.assertLess(adjusted.iloc[-1], 50.0)

    def test_new_entry_stays_in_cash_without_buy_signal(self):
        dates = pd.date_range("2020-01-01", periods=4, freq="B")
        prices = pd.DataFrame({"Open": [100, 90, 80, 70], "Close": [100, 90, 80, 70]}, index=dates)
        herd = pd.Series(50.0, index=dates)
        trend = pd.DataFrame({"trend_quality": 50}, index=dates)
        result = run_realistic_strategy(
            "TEST", prices, herd, trend, self._hold, investor=InvestorConfig("new_entry"),
        )
        self.assertEqual(result.portfolio_values, [10_000.0] * 4)
        self.assertEqual(result.mdd, 0.0)

    def test_monthly_dca_adjusts_return_for_external_contributions(self):
        dates = pd.to_datetime(["2020-01-31", "2020-02-03", "2020-03-02"])
        prices = pd.DataFrame({"Open": [100, 100, 100], "Close": [100, 100, 100]}, index=dates)
        herd = pd.Series(50.0, index=dates)
        trend = pd.DataFrame({"trend_quality": 50}, index=dates)
        result = run_realistic_strategy(
            "TEST", prices, herd, trend, self._hold,
            ExecutionConfig(fee_rate=0, slippage_bps=0),
            InvestorConfig("monthly_dca", monthly_contribution=500),
        )
        self.assertEqual(result.contributions, 1_000.0)
        self.assertEqual(result.portfolio_values[-1], 11_000.0)
        self.assertAlmostEqual(result.return_pct, 0.0)

    def test_monthly_dca_does_not_reinvest_existing_cash(self):
        dates = pd.to_datetime(["2020-01-31", "2020-02-03", "2020-02-04"])
        prices = pd.DataFrame({"Open": [100, 100, 50], "Close": [100, 100, 50]}, index=dates)
        herd = pd.Series([80.0, 80.0, 80.0], index=dates)
        trend = pd.DataFrame({"trend_quality": 50}, index=dates)
        def sell(_score, _trend, _previous, _days): return "SELL", 0.5
        result = run_realistic_strategy(
            "TEST", prices, herd, trend, sell,
            ExecutionConfig(fee_rate=0, slippage_bps=0, cooldown_days=20),
            InvestorConfig("monthly_dca", monthly_contribution=500),
        )
        self.assertEqual(result.contributions, 500)
        self.assertEqual(result.portfolio_values[-1], 7_750)
        self.assertEqual(len(result.trades), 1)

    def test_target_rebalance_starts_at_configured_weight(self):
        dates = pd.date_range("2020-01-01", periods=2, freq="B")
        prices = pd.DataFrame({"Open": [100, 100], "Close": [100, 100]}, index=dates)
        herd = pd.Series(50.0, index=dates)
        trend = pd.DataFrame({"trend_quality": 50}, index=dates)
        result = run_realistic_strategy(
            "TEST", prices, herd, trend, self._hold,
            ExecutionConfig(fee_rate=0, slippage_bps=0),
            InvestorConfig("target_rebalance", target_stock_weight=0.7),
        )
        self.assertEqual(result.portfolio_values, [10_000.0, 10_000.0])
        self.assertEqual(result.investor_scenario, "target_rebalance")


if __name__ == "__main__":
    unittest.main()
