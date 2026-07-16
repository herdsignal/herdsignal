import unittest

import pandas as pd

from herd.action_accuracy import collect_action_events, summarize_action_accuracy


class ActionAccuracyTest(unittest.TestCase):
    def setUp(self):
        self.dates = pd.date_range("2020-01-01", periods=160, freq="B")
        self.prices = pd.DataFrame({
            "Open": range(100, 260), "Close": range(100, 260),
        }, index=self.dates, dtype=float)
        self.herd = pd.Series(10.0, index=self.dates)
        self.trend = pd.DataFrame({"return_63d": 10.0}, index=self.dates)

    def test_buy_event_has_forward_windows_and_positive_counterfactual(self):
        def buy(_score, _trend, _previous, _days): return "BUY", 0.2
        events = collect_action_events(self.prices, self.herd, self.trend, buy, cooldown_days=20)
        first = events[0]
        self.assertGreater(first["return_1m"], 0)
        self.assertGreater(first["counterfactual_delta_3m"], 0)
        self.assertEqual(first["herd_stage"], "flee")
        self.assertEqual(first["market_regime"], "bull")

    def test_sell_counterfactual_rewards_avoided_decline(self):
        falling = self.prices.copy()
        falling["Open"] = falling["Close"] = list(range(260, 100, -1))
        def sell(_score, _trend, _previous, _days): return "SELL", 0.1
        events = collect_action_events(falling, pd.Series(80.0, index=self.dates), self.trend, sell)
        self.assertGreater(events[0]["counterfactual_delta_3m"], 0)
        self.assertTrue(events[0]["hit_3m"])

    def test_summary_groups_ratio_lifecycle_stage_and_regime(self):
        def buy(_score, _trend, _previous, _days): return "BUY", 0.2
        summary = summarize_action_accuracy(collect_action_events(self.prices, self.herd, self.trend, buy))
        self.assertIn("15-30%", summary["by_ratio"])
        self.assertIn("early", summary["by_lifecycle"])
        self.assertIn("flee", summary["by_herd_stage"])
        self.assertIn("bull", summary["by_market_regime"])

    def test_summary_reports_completed_samples_for_each_horizon(self):
        def buy(_score, _trend, _previous, _days): return "BUY", 0.2
        summary = summarize_action_accuracy(collect_action_events(self.prices, self.herd, self.trend, buy))
        self.assertGreater(summary["horizons"]["1m"]["samples"], summary["horizons"]["6m"]["samples"])
        self.assertEqual(summary["horizons"]["1m"]["hit_rate"], 100)


if __name__ == "__main__":
    unittest.main()
