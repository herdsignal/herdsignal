import unittest

from herd.validation_diagnostics import diagnose, enrich, market_regime


def row(ticker="AAPL", year=2022, bh=20, fixed=10, v61=12, fixed_mdd=-20, v61_mdd=-15):
    return {"ticker": ticker, "test_start": year, "mode": "rolling", "buyhold_return": bh,
            "fixed_return": fixed, "v61_return": v61, "fixed_mdd": fixed_mdd, "v61_mdd": v61_mdd,
            "ratio_scale": 1.0, "cooldown_days": 20}


class ValidationDiagnosticsTest(unittest.TestCase):
    def test_market_regime_boundaries(self):
        self.assertEqual(market_regime(-10), "bear")
        self.assertEqual(market_regime(0), "sideways")
        self.assertEqual(market_regime(10), "bull")

    def test_enrich_marks_bull_capture_failure(self):
        result = enrich(row(v61=5))
        self.assertFalse(result["return_improved"])
        self.assertIn("bull_market_capture_failure", result["failure_reasons"])

    def test_diagnose_groups_failures(self):
        report = diagnose([row(), row(ticker="MSFT", bh=-20, v61=5, v61_mdd=-25)])
        self.assertEqual(report["summary"]["samples"], 2)
        self.assertEqual(len(report["by_market_regime"]), 2)
        self.assertGreater(report["summary"]["failure_reasons"]["worse_mdd_than_fixed"], 0)

    def test_equal_result_is_not_failure(self):
        result = enrich(row(v61=10.01, v61_mdd=-20.01))
        self.assertEqual(result["return_status"], "equal")
        self.assertEqual(result["mdd_status"], "equal")
        self.assertTrue(result["joint_pass"])


if __name__ == "__main__": unittest.main()
