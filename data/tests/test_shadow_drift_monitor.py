import unittest
from datetime import date

from herd.shadow_drift_monitor import ShadowDriftThresholds, evaluate_shadow_drift


class ShadowDriftMonitorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.thresholds = ShadowDriftThresholds(minimum_observations=3)

    def test_consistent_complete_observations_are_ready_for_observation_only(self) -> None:
        rows = [
            {
                "observed_on": "2026-07-21",
                "ticker": ticker,
                "production_score": 60,
                "shadow_score": score,
                "production_action": "HOLD",
                "shadow_action": "HOLD",
            }
            for ticker, score in (("A", 61), ("B", 65), ("C", 68))
        ]

        result = evaluate_shadow_drift(
            rows, as_of=date(2026, 7, 21), thresholds=self.thresholds
        )

        self.assertEqual(result["status"], "OBSERVATION_READY")
        self.assertFalse(result["promotion_authorized"])
        self.assertEqual(result["failed_checks"], [])

    def test_missing_and_stale_rows_fail_closed(self) -> None:
        rows = [
            {
                "observed_on": "2026-07-20",
                "ticker": "A",
                "production_score": 60,
                "shadow_score": None,
                "production_action": "HOLD",
                "shadow_action": None,
            }
        ] * 3

        result = evaluate_shadow_drift(
            rows, as_of=date(2026, 7, 21), thresholds=self.thresholds
        )

        self.assertEqual(result["status"], "BLOCKED_DRIFT_REVIEW")
        self.assertIn("coverage", result["failed_checks"])
        self.assertIn("stale_rate", result["failed_checks"])

    def test_large_score_and_action_divergence_is_reported(self) -> None:
        rows = [
            {
                "observed_on": "2026-07-21",
                "ticker": ticker,
                "production_score": 20,
                "shadow_score": 80,
                "production_action": "HOLD",
                "shadow_action": "SELL",
            }
            for ticker in ("A", "B", "C")
        ]

        result = evaluate_shadow_drift(
            rows, as_of=date(2026, 7, 21), thresholds=self.thresholds
        )

        self.assertIn("score_p95_absolute_error", result["failed_checks"])
        self.assertIn("action_disagreement_rate", result["failed_checks"])

    def test_empty_input_never_passes(self) -> None:
        result = evaluate_shadow_drift(
            [], as_of=date(2026, 7, 21), thresholds=self.thresholds
        )

        self.assertEqual(result["status"], "BLOCKED_DRIFT_REVIEW")
        self.assertFalse(result["promotion_authorized"])
