import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.pit_sensitivity_evaluation import (
    _conclusion,
    _drop_exclusion_windows,
    membership_intervals,
)


class PitSensitivityEvaluationTest(unittest.TestCase):
    def test_builds_end_exclusive_membership_intervals(self):
        intervals = membership_intervals(
            [{"scenario": "S", "ticker": "OLD"}],
            [{
                "scenario": "S",
                "effective_date": "2020-01-03",
                "added": "NEW",
                "removed": "OLD",
            }],
            period_start="2020-01-01",
            period_end="2020-01-10",
        )
        self.assertEqual(
            [(pd.Timestamp("2020-01-01"), pd.Timestamp("2020-01-03"))],
            intervals["S"]["OLD"],
        )
        self.assertEqual(
            [(pd.Timestamp("2020-01-03"), pd.Timestamp("2020-01-11"))],
            intervals["S"]["NEW"],
        )

    def test_flags_candidate_ranking_change(self):
        scenarios = {
            "A": {
                "B0": {"strategy": {"excess_cagr": 0.01}},
                "B1": {"strategy": {"excess_cagr": 0.02}},
            },
            "B": {
                "B0": {"strategy": {"excess_cagr": 0.03}},
                "B1": {"strategy": {"excess_cagr": 0.01}},
            },
        }
        conclusion = _conclusion(scenarios)
        self.assertFalse(conclusion["ranking_stable"])
        self.assertTrue(conclusion["decision_sensitive"])

    def test_does_not_exclude_nearest_rows_outside_observed_period(self):
        frame = pd.DataFrame({
            "ticker": ["LIN", "LIN"],
            "date": pd.to_datetime(["2020-01-02", "2020-01-03"]),
        })
        filtered, count = _drop_exclusion_windows(
            frame,
            [{
                "ticker": "LIN",
                "center_date": "2018-10-31",
                "observations_before": "63",
                "observations_after": "63",
            }],
        )
        self.assertEqual(0, count)
        self.assertEqual(2, len(filtered))


if __name__ == "__main__":
    unittest.main()
