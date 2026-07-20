import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.rush_turning_point_oos import (
    extract_transition_events,
    select_non_overlapping_events,
)


class RushTurningPointOosTest(unittest.TestCase):
    def test_only_first_month_of_a_state_is_an_event(self):
        dates = pd.date_range("2024-01-31", periods=4, freq="ME")
        states = pd.DataFrame(
            {
                "AAA": [
                    "HEALTHY_RUSH",
                    "HEALTHY_RUSH",
                    "EXHAUSTED_RUSH",
                    "EXHAUSTED_RUSH",
                ]
            },
            index=dates,
        )
        events = extract_transition_events(states)
        self.assertEqual(
            events["state"].tolist(),
            ["HEALTHY_RUSH", "EXHAUSTED_RUSH"],
        )

    def test_overlapping_events_are_removed_per_ticker_and_fold(self):
        events = pd.DataFrame([
            {
                "signal_date": pd.Timestamp("2024-01-31"),
                "ticker": "AAA",
                "state": "HEALTHY_RUSH",
                "horizon_months": 3,
                "outcome_end": pd.Timestamp("2024-04-30"),
                "fold_id": "F01",
            },
            {
                "signal_date": pd.Timestamp("2024-03-31"),
                "ticker": "AAA",
                "state": "EXHAUSTED_RUSH",
                "horizon_months": 3,
                "outcome_end": pd.Timestamp("2024-06-30"),
                "fold_id": "F01",
            },
            {
                "signal_date": pd.Timestamp("2024-05-31"),
                "ticker": "AAA",
                "state": "BREAKING_RUSH",
                "horizon_months": 3,
                "outcome_end": pd.Timestamp("2024-08-31"),
                "fold_id": "F01",
            },
        ])
        selected = select_non_overlapping_events(events)
        self.assertEqual(
            selected["signal_date"].tolist(),
            [pd.Timestamp("2024-01-31"), pd.Timestamp("2024-05-31")],
        )


if __name__ == "__main__":
    unittest.main()
