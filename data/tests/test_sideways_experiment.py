import unittest

import pandas as pd

from herd.sideways_experiment import is_sideways, summarize_experiment, suppress_decision


class SidewaysExperimentTest(unittest.TestCase):
    def test_sideways_requires_flat_return_and_neutral_quality(self):
        self.assertTrue(is_sideways(pd.Series({"trend_quality": 50, "return_63d": 3})))
        self.assertFalse(is_sideways(pd.Series({"trend_quality": 80, "return_63d": 3})))
        self.assertFalse(is_sideways(pd.Series({"trend_quality": 50, "return_63d": 12})))

    def test_suppresses_only_sideways_ratio(self):
        base = lambda *_args: ("SELL", 0.2)
        decide = suppress_decision(base, 0.5)
        self.assertEqual(decide(70, pd.Series({"trend_quality": 50, "return_63d": 2}), None, 1), ("SELL", 0.1))
        self.assertEqual(decide(70, pd.Series({"trend_quality": 80, "return_63d": 2}), None, 1), ("SELL", 0.2))

    def test_summarizes_candidate_against_baseline(self):
        rows = [{"candidate_return": 12, "baseline_return": 10, "candidate_mdd": -8, "baseline_mdd": -10,
                 "candidate_actions": 3, "baseline_actions": 5}]
        result = summarize_experiment(rows)
        self.assertEqual(result["return_improvement_rate"], 100)
        self.assertEqual(result["trade_reduction_median"], 2)


if __name__ == "__main__": unittest.main()
