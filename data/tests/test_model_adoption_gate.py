import unittest

from herd.model_adoption_gate import evaluate_adoption_gate


def _passing_metadata() -> dict:
    return {
        "validation_run": {"status": "COMPLETE", "coverage": 1.0},
        "score_parity": {"passed": True},
        "walk_forward_summary": {
            "improvement_rate": 65.0,
            "mdd_improvement_median": 1.0,
            "capture_bottom_decile_mean": 70.0,
        },
        "parameter_stability": {
            "single_parameter_spike": False,
            "transition_stability": {"same_parameter_rate": 75.0},
        },
        "overfitting": {
            "cscv": {"pbo": 0.1},
            "deflated_sharpe": {"probability": 0.97},
        },
        "survivorship_coverage": {"point_in_time_ready": True, "status": "POINT_IN_TIME_READY"},
    }


class ModelAdoptionGateTest(unittest.TestCase):
    def test_passing_model_becomes_review_candidate_not_production(self) -> None:
        result = evaluate_adoption_gate(_passing_metadata())

        self.assertEqual(result["status"], "PROMOTION_CANDIDATE")
        self.assertTrue(result["eligible_for_human_review"])
        self.assertFalse(result["automatic_production_promotion"])
        self.assertEqual(result["failed_criteria"], [])

    def test_missing_or_failed_metrics_fail_closed(self) -> None:
        metadata = _passing_metadata()
        metadata["overfitting"]["deflated_sharpe"]["probability"] = None
        metadata["survivorship_coverage"] = {}

        result = evaluate_adoption_gate(metadata)

        self.assertEqual(result["status"], "RESEARCH_VALIDATION")
        self.assertIn("deflated_sharpe", result["failed_criteria"])
        self.assertIn("survivorship", result["failed_criteria"])
