import unittest
import pandas as pd

from herd.risk_cap_experiment import capped_decision, summarize_risk_cap


class RiskCapExperimentTest(unittest.TestCase):
    def test_caps_buy_in_weak_trend(self):
        decide = capped_decision(lambda *_: ("BUY", 0.2), "balanced")
        self.assertEqual(decide(10, pd.Series({"trend_quality": 40, "return_63d": -12}), None, 1), ("BUY", 0.05))

    def test_caps_sell_in_strong_trend(self):
        decide = capped_decision(lambda *_: ("SELL", 0.3), "strict")
        self.assertEqual(decide(90, pd.Series({"trend_quality": 80, "return_63d": 20}), None, 1), ("SELL", 0.05))

    def test_off_preserves_decision(self):
        decide = capped_decision(lambda *_: ("SELL", 0.3), "off")
        self.assertEqual(decide(90, pd.Series(), None, 1), ("SELL", 0.3))

    def test_summary_reports_joint_improvement(self):
        rows = [{"candidate_return": 11, "baseline_return": 10, "candidate_mdd": -8, "baseline_mdd": -10,
                 "candidate_actions": 4, "baseline_actions": 5}]
        self.assertEqual(summarize_risk_cap(rows)["joint_improvement_rate"], 100)


if __name__ == "__main__": unittest.main()
