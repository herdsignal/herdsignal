import unittest

from herd.model_adoption_gate import evaluate_adoption_gate


def _passing_metadata() -> dict:
    return {
        "validation_run": {
            "status": "COMPLETE",
            "coverage": 1.0,
            "universe_size": 55,
            "oos_years": 7.0,
        },
        "score_parity": {"passed": True},
        "parameter_policy": {"mode": "fixed", "automatic_selection_applied": False},
        "benchmark_summary": {
            "median_excess_cagr": 0.012,
            "positive_excess_rate": 63.0,
            "median_upside_capture": 0.91,
            "median_downside_capture": 0.78,
            "median_average_exposure": 0.91,
        },
        "cost_stress": {"median_excess_cagr": 0.004},
        "action_efficacy": {
            "status": "COMPLETE",
            "required_metrics_complete": True,
        },
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
        "blind_holdout": {"status": "COMPLETE", "evaluation_count": 1, "passed": True},
    }


class ModelAdoptionGateTest(unittest.TestCase):
    def test_complete_pre_holdout_gate_does_not_require_opening_holdout(self) -> None:
        metadata = _passing_metadata()
        metadata.pop("blind_holdout")

        result = evaluate_adoption_gate(metadata, stage="PRE_HOLDOUT")

        self.assertEqual(result["status"], "READY_FOR_BLIND_HOLDOUT")
        self.assertTrue(result["eligible_for_holdout"])
        self.assertFalse(result["eligible_for_human_review"])
        self.assertNotIn("blind_holdout_single_use", [
            criterion["name"] for criterion in result["criteria"]
        ])

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

    def test_buy_and_hold_underperformance_cannot_pass(self) -> None:
        metadata = _passing_metadata()
        metadata["benchmark_summary"]["median_excess_cagr"] = -0.001
        metadata["benchmark_summary"]["positive_excess_rate"] = 70.0

        result = evaluate_adoption_gate(metadata)

        self.assertFalse(result["eligible_for_human_review"])
        self.assertIn("median_excess_cagr", result["failed_criteria"])

    def test_reusing_blind_holdout_cannot_pass(self) -> None:
        metadata = _passing_metadata()
        metadata["blind_holdout"]["evaluation_count"] = 2

        result = evaluate_adoption_gate(metadata)

        self.assertIn("blind_holdout_single_use", result["failed_criteria"])

    def test_low_exposure_or_incomplete_cycles_cannot_pass(self) -> None:
        metadata = _passing_metadata()
        metadata["benchmark_summary"]["median_average_exposure"] = 0.79
        metadata["action_efficacy"]["required_metrics_complete"] = False

        result = evaluate_adoption_gate(metadata)

        self.assertIn("average_exposure", result["failed_criteria"])
        self.assertIn(
            "completed_action_cycle_metrics",
            result["failed_criteria"],
        )
