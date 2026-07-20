import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.blind_holdout_gate import decide


def _passed_pre_holdout_gate() -> dict:
    return {
        "stage": "PRE_HOLDOUT",
        "status": "READY_FOR_BLIND_HOLDOUT",
        "eligible_for_holdout": True,
        "failed_criteria": [],
    }


class BlindHoldoutGateTest(unittest.TestCase):
    def test_failed_candidate_never_opens_holdout(self):
        candidate = {
            "summary": {
                "B0": {
                    "median_excess_cagr": -0.01,
                    "positive_excess_rate": 40,
                    "median_upside_capture": 0.95,
                    "median_downside_capture": 0.90,
                    "median_mdd_improvement": 0.01,
                }
            }
        }
        quality = {
            "summary": {
                "overall_status": "READY",
                "point_in_time_universe_ready": True,
            }
        }
        generalization = {
            "walk_forward": {"status": "COMPLETE"},
            "era_validation": {"status": "COMPLETE"},
        }

        result = decide(
            candidate, quality, generalization, _passed_pre_holdout_gate()
        )

        self.assertEqual(result["status"], "NOT_OPENED_PREREQUISITES_FAILED")
        self.assertEqual(result["evaluation_count"], 0)
        self.assertFalse(result["sealed_data_accessed"])

    def test_all_preconditions_only_make_holdout_ready(self):
        candidate = {
            "summary": {
                "B0": {
                    "median_excess_cagr": 0.01,
                    "positive_excess_rate": 65,
                    "median_upside_capture": 0.90,
                    "median_downside_capture": 0.80,
                    "median_mdd_improvement": 0.01,
                }
            }
        }
        quality = {
            "summary": {
                "overall_status": "READY",
                "point_in_time_universe_ready": True,
            }
        }
        generalization = {
            "walk_forward": {"status": "COMPLETE"},
            "era_validation": {"status": "COMPLETE"},
        }

        result = decide(
            candidate, quality, generalization, _passed_pre_holdout_gate()
        )

        self.assertEqual(result["status"], "READY_TO_OPEN")
        self.assertEqual(result["evaluation_count"], 0)
        self.assertIsNone(result["passed"])

    def test_summary_metrics_cannot_bypass_full_pre_holdout_gate(self):
        candidate = {
            "summary": {
                "B9": {
                    "median_excess_cagr": 0.02,
                    "positive_excess_rate": 70,
                    "median_upside_capture": 0.90,
                    "median_downside_capture": 0.80,
                    "median_mdd_improvement": 0.01,
                }
            }
        }
        quality = {
            "summary": {
                "overall_status": "READY",
                "point_in_time_universe_ready": True,
            }
        }
        generalization = {
            "walk_forward": {"status": "COMPLETE"},
            "era_validation": {"status": "COMPLETE"},
        }
        failed_gate = {
            "stage": "PRE_HOLDOUT",
            "status": "RESEARCH_VALIDATION",
            "eligible_for_holdout": False,
            "failed_criteria": ["pbo", "deflated_sharpe"],
        }

        result = decide(candidate, quality, generalization, failed_gate)

        self.assertEqual(result["status"], "NOT_OPENED_PREREQUISITES_FAILED")
        self.assertIn("full_pre_holdout_gate_passed", result["failed_prerequisites"])


if __name__ == "__main__":
    unittest.main()
