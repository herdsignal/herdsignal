import unittest

from herd.overfitting_metrics import analyze_overfitting, cscv_pbo, deflated_sharpe_ratio


class OverfittingMetricsTest(unittest.TestCase):
    def test_cscv_detects_inconsistent_winner(self):
        history = []
        for fold in range(6):
            history += [
                {"evaluation_id": fold, "candidate_id": "A", "objective": 10 if fold < 3 else -10},
                {"evaluation_id": fold, "candidate_id": "B", "objective": 0},
            ]
        result = cscv_pbo(history)
        self.assertGreater(result["splits"], 0)
        self.assertIsNotNone(result["pbo"])

    def test_dsr_records_trial_penalty(self):
        result = deflated_sharpe_ratio([1, 2, -1, 3, 1, 2], 9)
        self.assertEqual(result["trials"], 9)
        self.assertIn(result["status"], {"PASS", "FAIL"})

    def test_report_contains_history_count_and_sensitivity(self):
        history = [{"evaluation_id": fold, "candidate_id": candidate, "objective": fold + index}
                   for fold in range(4) for index, candidate in enumerate(("A", "B"))]
        report = analyze_overfitting(history, [{"v61_return": value} for value in (1, 2, -1, 3)])
        self.assertEqual(report["candidate_evaluations"], 8)
        self.assertEqual(report["parameters_tested"], 2)
        self.assertIn("A", report["parameter_sensitivity"])


if __name__ == "__main__": unittest.main()
