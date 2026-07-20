import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.business_guard_oos import (
    extract_guard_transitions,
    select_non_overlapping_events,
)


class BusinessGuardOosTest(unittest.TestCase):
    def test_only_guard_state_transitions_become_events(self):
        features = pd.DataFrame({
            "ticker": ["AAA"] * 5,
            "month_end": pd.date_range("2024-01-31", periods=5, freq="ME"),
            "guard_state": ["UNKNOWN", "PASS", "PASS", "VETO", "VETO"],
        })
        events = extract_guard_transitions(features)
        self.assertEqual(events["guard_state"].tolist(), ["PASS", "VETO"])

    def test_non_overlapping_events_are_selected_per_ticker(self):
        events = pd.DataFrame([
            {
                "signal_date": pd.Timestamp("2024-01-31"),
                "ticker": "AAA",
                "horizon_months": 3,
                "outcome_end": pd.Timestamp("2024-04-30"),
                "fold_id": "F01",
            },
            {
                "signal_date": pd.Timestamp("2024-03-31"),
                "ticker": "AAA",
                "horizon_months": 3,
                "outcome_end": pd.Timestamp("2024-06-30"),
                "fold_id": "F01",
            },
        ])
        selected = select_non_overlapping_events(events)
        self.assertEqual(len(selected), 1)


if __name__ == "__main__":
    unittest.main()
