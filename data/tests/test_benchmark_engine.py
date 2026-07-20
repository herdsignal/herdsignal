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
    simulate_fractional_actions,
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
            "terminal_wealth_delta", "terminal_share_delta",
            "total_fees", "estimated_slippage_cost",
        ):
            self.assertIn(key, metrics)

    def test_fractional_action_executes_next_day_and_uses_holding_fraction(self):
        prices = _prices([100, 100, 100])
        actions = pd.DataFrame(
            {"action": ["SELL", "HOLD", "HOLD"], "ratio": [0.25, 0.0, 0.0]},
            index=prices.index,
        )
        result = simulate_fractional_actions(
            "legacy",
            prices,
            actions,
            config=BenchmarkConfig(fee_rate=0.0, slippage_rate=0.0),
        )

        sell = result.trades[-1]
        self.assertEqual(sell.execution_date, prices.index[1])
        self.assertAlmostEqual(sell.shares, result.trades[0].shares * 0.25)

    def test_comparison_rejects_different_cost_assumptions(self):
        prices = _prices([100, 101, 102])
        benchmark = buy_and_hold(
            prices,
            config=BenchmarkConfig(fee_rate=0.0, slippage_rate=0.0),
        )
        strategy = simulate(
            "strategy",
            prices,
            pd.Series(1.0, index=prices.index),
            config=BenchmarkConfig(fee_rate=0.001, slippage_rate=0.0),
        )

        with self.assertRaisesRegex(ValueError, "execution costs"):
            performance_metrics(strategy, benchmark)

    def test_comparison_rejects_different_dates(self):
        prices = _prices([100, 101, 102, 103])
        benchmark = buy_and_hold(
            prices,
            config=BenchmarkConfig(fee_rate=0.0, slippage_rate=0.0),
        )
        shorter = prices.iloc[1:]
        strategy = simulate(
            "strategy",
            shorter,
            pd.Series(1.0, index=shorter.index),
            config=BenchmarkConfig(fee_rate=0.0, slippage_rate=0.0),
        )

        with self.assertRaisesRegex(ValueError, "identical dates"):
            performance_metrics(strategy, benchmark)

    def test_terminal_share_delta_tracks_incomplete_reentry(self):
        prices = _prices([100, 100, 100])
        config = BenchmarkConfig(fee_rate=0.0, slippage_rate=0.0)
        benchmark = buy_and_hold(prices, config=config)
        actions = pd.DataFrame(
            {"action": ["SELL", "HOLD", "HOLD"], "ratio": [0.10, 0.0, 0.0]},
            index=prices.index,
        )
        strategy = simulate_fractional_actions(
            "incomplete-cycle", prices, actions, config=config
        )

        metrics = performance_metrics(strategy, benchmark)
        self.assertLess(metrics["terminal_share_delta"], 0.0)
        self.assertAlmostEqual(
            metrics["terminal_wealth_delta"], 0.0, places=8
        )


if __name__ == "__main__":
    unittest.main()
