import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.candidate_model_evaluation import build_candidate_targets, classify_rush


class CandidateModelEvaluationTest(unittest.TestCase):
    def test_rush_requires_confirmation_to_be_healthy(self):
        index = pd.to_datetime(["2025-01-31", "2025-02-28"])
        trend = pd.Series([80.0, 80.0], index=index)
        participation = pd.Series([70.0, 30.0], index=index)
        risk = pd.Series([60.0, 60.0], index=index)

        result = classify_rush(trend, participation, risk)

        self.assertEqual(result.tolist(), ["HEALTHY_RUSH", "EXHAUSTED_RUSH"])

    def test_risk_is_exposure_cap_not_directional_score(self):
        month = pd.to_datetime(["2025-01-31"])
        daily = pd.to_datetime(["2025-01-31", "2025-02-03"])
        scores = {
            "trend_relative_strength": pd.Series([80.0], index=month),
            "participation": pd.Series([80.0], index=month),
            "risk": pd.Series([10.0], index=month),
        }
        targets = build_candidate_targets(
            scores,
            daily,
            v4_score=pd.Series([50.0], index=month),
        )

        self.assertEqual(targets["B2"].dropna().iloc[0], 1.0)
        self.assertEqual(targets["B3"].dropna().iloc[0], 0.75)


if __name__ == "__main__":
    unittest.main()
