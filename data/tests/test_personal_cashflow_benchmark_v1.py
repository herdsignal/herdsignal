import json
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.benchmark_engine import BenchmarkConfig
from herd.personal_cashflow_benchmark_v1 import (
    CashflowBenchmarkError,
    attribute_result,
    build_external_cashflows,
    compare_with_matched_buy_and_hold,
    load_contract,
    validate_contract,
)


def _prices(periods: int = 520, daily_growth: float = 0.0003) -> pd.DataFrame:
    index = pd.date_range("2023-01-02", periods=periods, freq="B")
    close = pd.Series(
        [100.0 * ((1 + daily_growth) ** position) for position in range(periods)],
        index=index,
    )
    return pd.DataFrame({"Open": close, "Close": close}, index=index)


class PersonalCashflowBenchmarkV1Test(unittest.TestCase):
    def test_contract_is_locked_and_non_operational(self):
        report = validate_contract(load_contract())
        self.assertEqual(report["status"], "CASHFLOW_BENCHMARK_CONTRACT_VERIFIED")
        self.assertFalse(report["operational_action_authority"])

    def test_fixed_monthly_flow_excludes_start_month(self):
        prices = _prices(70)
        flows = build_external_cashflows(
            prices.index,
            "FIXED_MONTHLY_NEW_CASH",
            monthly_amount=500.0,
        )
        self.assertEqual(float(flows.iloc[0]), 0.0)
        self.assertEqual(set(flows[flows > 0].tolist()), {500.0})
        self.assertEqual(int((flows > 0).sum()), 3)

    def test_observed_flows_reject_future_or_negative_values(self):
        prices = _prices(10)
        outside = pd.Series([100.0], index=[pd.Timestamp("2030-01-01")])
        with self.assertRaisesRegex(CashflowBenchmarkError, "outside"):
            build_external_cashflows(
                prices.index,
                "OBSERVED_PERSONAL_CASHFLOWS",
                observed=outside,
            )
        negative = pd.Series([-1.0], index=[prices.index[2]])
        with self.assertRaisesRegex(CashflowBenchmarkError, "non-negative"):
            build_external_cashflows(
                prices.index,
                "OBSERVED_PERSONAL_CASHFLOWS",
                observed=negative,
            )

    def test_matched_comparison_uses_identical_external_flows(self):
        prices = _prices()
        flows = build_external_cashflows(
            prices.index,
            "FIXED_MONTHLY_NEW_CASH",
            monthly_amount=300.0,
        )
        targets = pd.Series(1.0, index=prices.index)
        comparison = compare_with_matched_buy_and_hold(
            "FIXED_MONTHLY_NEW_CASH",
            prices,
            targets,
            flows,
            config=BenchmarkConfig(fee_rate=0.0, slippage_rate=0.0),
        )
        pd.testing.assert_series_equal(
            comparison.strategy.external_flows,
            comparison.benchmark.external_flows,
        )
        self.assertAlmostEqual(
            float(comparison.comparison_metrics["terminal_wealth_delta"]),
            0.0,
        )
        self.assertAlmostEqual(
            comparison.strategy_attribution.investment_gain,
            comparison.benchmark_attribution.investment_gain,
        )

    def test_twr_removes_contributions_while_mwr_reflects_timing(self):
        prices = _prices()
        flows = build_external_cashflows(
            prices.index,
            "FIXED_MONTHLY_NEW_CASH",
            monthly_amount=500.0,
        )
        comparison = compare_with_matched_buy_and_hold(
            "FIXED_MONTHLY_NEW_CASH",
            prices,
            pd.Series(1.0, index=prices.index),
            flows,
            config=BenchmarkConfig(fee_rate=0.0, slippage_rate=0.0),
        )
        attribution = attribute_result(comparison.strategy)
        self.assertIsNotNone(attribution.annualized_time_weighted_return)
        self.assertIsNotNone(attribution.annualized_money_weighted_return)
        self.assertNotAlmostEqual(
            attribution.time_weighted_return,
            attribution.final_equity / attribution.initial_capital - 1.0,
        )

    def test_contract_rejects_single_scenario_promotion(self):
        contract = json.loads(json.dumps(load_contract()))
        contract["promotion_boundary"]["single_cashflow_scenario_is_insufficient"] = False
        with self.assertRaisesRegex(CashflowBenchmarkError, "cannot authorize"):
            validate_contract(contract)


if __name__ == "__main__":
    unittest.main()
