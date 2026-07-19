import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.candidate_generalization import analyze


class CandidateGeneralizationTest(unittest.TestCase):
    def test_missing_time_folds_fail_closed(self):
        rows = []
        for ticker, a, b in (("SPY", 0.01, -0.01), ("QQQ", -0.02, 0.01),
                             ("IWM", 0.00, -0.01), ("DIA", 0.01, 0.00)):
            rows.append(
                {
                    "ticker": ticker,
                    "candidates": {
                        "B0": {"excess_cagr": a},
                        "B1": {"excess_cagr": b},
                    },
                }
            )
        report = analyze({"summary": {"B0": {}, "B1": {}}, "rows": rows})

        self.assertEqual(report["decision"], "FAIL_CLOSED")
        self.assertEqual(report["walk_forward"]["status"], "INSUFFICIENT_DATA")
        self.assertLessEqual(report["cross_sectional_cscv"]["pbo"], 1.0)


if __name__ == "__main__":
    unittest.main()
