import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.legacy_model_evaluation import (
    _build_report,
    summarize,
    v4_actions,
)


class LegacyModelEvaluationTest(unittest.TestCase):
    def test_v4_actions_apply_directional_cooldown(self):
        index = pd.date_range("2025-01-01", periods=25, freq="B")
        actions = v4_actions(pd.Series([80.0] * 25, index=index))

        self.assertEqual(actions.iloc[0]["action"], "SELL")
        self.assertTrue((actions.iloc[1:21]["action"] == "HOLD").all())
        self.assertEqual(actions.iloc[21]["action"], "SELL")

    def test_summary_uses_median_and_positive_excess_rate(self):
        rows = [
            {"v4": {"cagr": 0.1, "excess_cagr": 0.02, "max_drawdown": -0.2,
                    "upside_capture": 0.9, "downside_capture": 0.8,
                    "turnover": 1.0, "trade_count": 2},
             "cost_stress": {"v4": {"excess_cagr": 0.01}}},
            {"v4": {"cagr": 0.05, "excess_cagr": -0.01, "max_drawdown": -0.1,
                    "upside_capture": 0.8, "downside_capture": 0.7,
                    "turnover": 2.0, "trade_count": 4},
             "cost_stress": {"v4": {"excess_cagr": -0.02}}},
        ]
        result = summarize(rows, "v4")

        self.assertAlmostEqual(result["median_excess_cagr"], 0.005)
        self.assertEqual(result["positive_excess_rate"], 50.0)

    def test_report_records_reproducible_data_source(self):
        report = _build_report(
            [],
            {"AAA": "failed"},
            period="10y",
            data_source={
                "mode": "IMMUTABLE_PRICE_SNAPSHOT",
                "reproducible": True,
                "snapshot_id": "test-snapshot",
            },
        )

        self.assertEqual(report["report_version"], "2026.07-v2")
        self.assertTrue(report["data_source"]["reproducible"])
        self.assertEqual(report["failures"], {"AAA": "failed"})


if __name__ == "__main__":
    unittest.main()
