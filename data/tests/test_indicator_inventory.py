import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.indicator_inventory import correlation_audit, inventory


class IndicatorInventoryTest(unittest.TestCase):
    def test_inventory_separates_market_reliability_and_personal_inputs(self):
        rows = {row["key"]: row for row in inventory()}

        self.assertEqual(rows["monthly_rsi"]["weight"], 0.24)
        self.assertEqual(rows["volume_strength"]["operating_status"], "disabled(weight=0)")
        self.assertEqual(rows["data_quality"]["family"], "reliability")
        self.assertEqual(rows["investor_profile"]["family"], "personal")
        self.assertTrue(rows["eps_multiplier"]["point_in_time_status"].startswith("unavailable"))

    def test_correlation_audit_flags_absolute_high_correlations_only(self):
        frame = pd.DataFrame({
            "a": range(20),
            "b": [value * 2 for value in range(20)],
            "c": list(reversed(range(20))),
            "d": [0, 4, 1, 3, 2] * 4,
        })

        report = correlation_audit(frame, threshold=0.85)
        pairs = {(row["left"], row["right"]): row for row in report["duplicate_candidates"]}

        self.assertEqual(pairs[("a", "b")]["spearman"], 1.0)
        self.assertEqual(pairs[("a", "c")]["spearman"], -1.0)
        self.assertNotIn(("a", "d"), pairs)
        self.assertEqual(report["observations"], 20)


if __name__ == "__main__":
    unittest.main()
