import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.evidence_family_validation import (
    _predictive_metrics,
    build_evidence_scores,
    score_to_targets,
)


class EvidenceFamilyValidationTest(unittest.TestCase):
    def setUp(self):
        index = pd.date_range("2023-01-02", periods=520, freq="B")
        self.closes = pd.DataFrame(
            {
                "UP": np.linspace(50, 150, len(index)),
                "DOWN": np.linspace(150, 50, len(index)),
                "FLAT": np.full(len(index), 100.0),
            },
            index=index,
        )
        self.volumes = pd.DataFrame(
            {
                "UP": np.linspace(100, 300, len(index)),
                "DOWN": np.linspace(300, 100, len(index)),
                "FLAT": np.full(len(index), 100.0),
            },
            index=index,
        )

    def test_builds_only_declared_market_evidence_families(self):
        result = build_evidence_scores(self.closes, self.volumes)

        self.assertEqual(
            set(result),
            {"participation", "trend_relative_strength", "risk"},
        )
        self.assertFalse(result["participation"].dropna(how="all").empty)
        self.assertGreater(
            result["trend_relative_strength"]["UP"].dropna().iloc[-1],
            result["trend_relative_strength"]["DOWN"].dropna().iloc[-1],
        )

    def test_fixed_score_thresholds_translate_to_exposure(self):
        monthly = pd.Series(
            [20.0, 50.0, 80.0],
            index=pd.to_datetime(["2025-01-31", "2025-02-28", "2025-03-31"]),
        )
        daily = pd.to_datetime(["2025-01-31", "2025-02-03", "2025-02-28", "2025-03-31"])

        result = score_to_targets(monthly, daily)

        self.assertEqual(result.dropna().tolist(), [0.0, 0.5, 1.0])
        self.assertTrue(pd.isna(result.iloc[1]))

    def test_predictive_metric_uses_future_return_only_as_target(self):
        index = pd.date_range("2018-01-31", periods=60, freq="ME")
        close = pd.Series(np.linspace(50, 150, len(index)), index=index)
        score = pd.Series(np.linspace(10, 90, len(index)), index=index)

        result = _predictive_metrics(score, close)

        self.assertIn("forward_12m_rank_ic", result)
        self.assertIsNotNone(result["high_minus_low_12m_return"])


if __name__ == "__main__":
    unittest.main()
