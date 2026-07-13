import unittest

import pandas as pd

from herd.healthy_rush import classify_rush, healthy_rush_decision


class HealthyRushTest(unittest.TestCase):
    def test_extending_rush_holds_strong_trend(self):
        regime, action, ratio = classify_rush(pd.Series({"trend_quality": 90, "ma200_deviation": 40,
                                                         "return_21d": 8, "return_63d": 20, "drawdown_52w": -2}))
        self.assertEqual((regime, action, ratio), ("EXTENDING_RUSH", "HOLD", 0.0))

    def test_exhausted_rush_takes_small_profit(self):
        regime, action, ratio = classify_rush(pd.Series({"trend_quality": 80, "ma200_deviation": 80,
                                                         "return_21d": -1, "return_63d": 20, "drawdown_52w": -9}))
        self.assertEqual(regime, "EXHAUSTED_RUSH")
        self.assertEqual(action, "SELL")
        self.assertLessEqual(ratio, 0.1)

    def test_breaking_rush_reduces_position(self):
        regime, action, ratio = classify_rush(pd.Series({"trend_quality": 30, "ma200_deviation": 10,
                                                         "return_21d": -10, "return_63d": -15, "drawdown_52w": -20}))
        self.assertEqual((regime, action, ratio), ("BREAKING_RUSH", "SELL", 0.2))

    def test_non_rush_uses_baseline(self):
        result = healthy_rush_decision(50, pd.Series(), lambda: ("BUY", 0.05))
        self.assertEqual(result, ("BUY", 0.05))


if __name__ == "__main__": unittest.main()
