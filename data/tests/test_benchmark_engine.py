import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.benchmark_engine import (
    BenchmarkConfig,
    buy_and_hold,
    performance_metrics,
    simulate,
)


def _prices(opens, closes=None):
    closes = closes or opens
    return pd.DataFrame(
        {"Open": opens, "Close": closes},
        index=pd.date_range("2025-01-01", periods=len(opens), freq="B"),
    )


class BenchmarkEngineTest(unittest.TestCase):
    def test_rejects_same_day_execution(self):
        with self.assertRaises(ValueError):
            BenchmarkConfig(execution_lag=0)

    def test_signal_executes_at_next_open_with_costs(self):
        prices = _prices([100, 110, 120], [100, 110, 120])
        targets = pd.Series([0.0, float("nan"), float("nan")], index=prices.index)
        result = simulate(
            "strategy",
            prices,
            targets,
            config=BenchmarkConfig(fee_rate=0.0, slippage_rate=0.0, initial_weight=1.0),
        )

        sell = result.trades[-1]
        self.assertEqual(sell.signal_date, prices.index[0])
        self.assertEqual(sell.execution_date, prices.index[1])
        self.assertEqual(sell.execution_price, 110)

    def test_identical_full_exposure_matches_buy_and_hold(self):
        prices = _prices([100, 101, 99, 105, 110])
        config = BenchmarkConfig(fee_rate=0.001, slippage_rate=0.0005)
        benchmark = buy_and_hold(prices, config=config)
        strategy = simulate(
            "strategy",
            prices,
            pd.Series(1.0, index=prices.index),
            config=config,
        )

        pd.testing.assert_series_equal(
            strategy.equity,
            benchmark.equity.rename("strategy"),
        )
        self.assertAlmostEqual(performance_metrics(strategy, benchmark)["excess_cagr"], 0.0)

    def test_contribution_is_not_counted_as_return(self):
        prices = _prices([100, 100, 100])
        contributions = pd.Series([0.0, 1_000.0, 0.0], index=prices.index)
        result = buy_and_hold(
            prices,
            config=BenchmarkConfig(fee_rate=0.0, slippage_rate=0.0),
            contributions=contributions,
        )

        self.assertAlmostEqual(float(result.daily_returns.iloc[1]), 0.0)
        self.assertEqual(result.contributed_capital, 11_000.0)

    def test_initial_execution_cost_is_included_in_return(self):
        prices = _prices([100, 100])
        result = buy_and_hold(
            prices,
            config=BenchmarkConfig(fee_rate=0.01, slippage_rate=0.0),
        )

        self.assertLess(float(result.daily_returns.iloc[0]), 0.0)
        self.assertLess(float(performance_metrics(result)["total_return"]), 0.0)

    def test_metrics_include_required_risk_and_capture_fields(self):
        prices = _prices([100, 110, 90, 120, 100, 130])
        config = BenchmarkConfig(fee_rate=0.0, slippage_rate=0.0)
        benchmark = buy_and_hold(prices, config=config)
        strategy = simulate(
            "strategy",
            prices,
            pd.Series([1.0, 0.5, 0.5, 1.0, 1.0, 1.0], index=prices.index),
            config=config,
        )
        metrics = performance_metrics(strategy, benchmark)

        for key in (
            "cagr", "max_drawdown", "sortino", "calmar",
            "upside_capture", "downside_capture", "turnover", "excess_cagr",
        ):
            self.assertIn(key, metrics)


if __name__ == "__main__":
    unittest.main()
