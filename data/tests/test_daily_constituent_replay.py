import unittest

from herd.daily_constituent_replay import ConstituentReplayError, replay_events


class DailyConstituentReplayTest(unittest.TestCase):
    def test_blocks_incomplete_ledger(self):
        with self.assertRaises(ConstituentReplayError):
            replay_events(
                {"AAA"},
                [{
                    "effective_date": "", "action": "ADD", "ticker": "BBB",
                    "event_status": "UNRESOLVED",
                }],
                minimum_size=1,
                maximum_size=2,
            )

    def test_applies_remove_before_add_on_same_date(self):
        ledger = [
            {
                "effective_date": "2024-01-02", "action": "ADD", "ticker": "BBB",
                "event_status": "VERIFIED_OFFICIAL_EVENT",
            },
            {
                "effective_date": "2024-01-02", "action": "REMOVE", "ticker": "AAA",
                "event_status": "VERIFIED_OFFICIAL_EVENT",
            },
        ]
        snapshots, audit = replay_events(
            {"AAA"}, ledger, minimum_size=1, maximum_size=1
        )
        self.assertEqual(["BBB"], snapshots[0]["added"])
        self.assertEqual(["AAA"], snapshots[0]["removed"])
        self.assertTrue(audit["replay_complete"])

    def test_diagnostic_records_absent_remove(self):
        ledger = [{
            "effective_date": "2024-01-02", "action": "REMOVE", "ticker": "MISSING",
            "event_status": "VERIFIED_OFFICIAL_EVENT",
        }, {
            "effective_date": "", "action": "ADD", "ticker": "UNKNOWN",
            "event_status": "REQUIRES_REVIEW",
        }]
        _, audit = replay_events(
            {"AAA"}, ledger, allow_diagnostic=True, minimum_size=1, maximum_size=2
        )
        self.assertEqual(1, audit["errors"])
        self.assertFalse(audit["replay_complete"])


if __name__ == "__main__":
    unittest.main()
