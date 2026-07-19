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

    def test_replays_identity_change_without_changing_count(self):
        snapshots, audit = replay_events(
            {"FB", "AAA"},
            [{
                "event_type": "IDENTITY_CHANGE",
                "effective_date": "2022-06-09",
                "action": "RENAME",
                "old_ticker": "FB",
                "ticker": "META",
                "event_status": "VERIFIED_IDENTITY_CHANGE",
            }],
            minimum_size=1,
            maximum_size=3,
        )
        self.assertEqual(["META"], snapshots[0]["added"])
        self.assertEqual(["FB"], snapshots[0]["removed"])
        self.assertEqual(2, audit["final_count"])
        self.assertTrue(audit["replay_complete"])

    def test_replays_verified_corporate_continuity(self):
        snapshots, audit = replay_events(
            {"OLD"},
            [{
                "event_type": "IDENTITY_CHANGE",
                "effective_date": "2019-11-05",
                "action": "RENAME",
                "old_ticker": "OLD",
                "ticker": "NEW",
                "event_status": "VERIFIED_CORPORATE_CONTINUITY",
            }],
            minimum_size=1,
            maximum_size=1,
        )
        self.assertEqual(["NEW"], snapshots[0]["added"])
        self.assertTrue(audit["replay_complete"])


if __name__ == "__main__":
    unittest.main()
