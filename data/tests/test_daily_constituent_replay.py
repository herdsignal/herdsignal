import unittest
from datetime import date

from herd.daily_constituent_replay import (
    ConstituentReplayError,
    apply_baseline_corrections,
    replay_events,
)


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

    def test_replays_admission_before_same_day_rename_by_sequence(self):
        snapshots, audit = replay_events(
            {"AAA"},
            [
                {
                    "event_type": "IDENTITY_CHANGE",
                    "index_effective_date": "2018-06-05",
                    "effective_date": "2018-06-05",
                    "event_sequence": "30",
                    "action": "RENAME",
                    "old_ticker": "WR",
                    "ticker": "EVRG",
                    "event_status": "VERIFIED_CORPORATE_CONTINUITY",
                },
                {
                    "event_type": "MEMBERSHIP_CHANGE",
                    "index_effective_date": "2018-06-05",
                    "effective_date": "2018-06-05",
                    "event_sequence": "20",
                    "action": "ADD",
                    "ticker": "WR",
                    "event_status": "VERIFIED_CORPORATE_CONTINUITY",
                },
            ],
            minimum_size=1,
            maximum_size=2,
        )
        self.assertEqual(["EVRG"], snapshots[0]["added"])
        self.assertEqual([], snapshots[0]["removed"])
        self.assertEqual(0, audit["errors"])
        self.assertTrue(audit["replay_complete"])

    def test_replay_uses_index_date_not_corporate_or_trading_date(self):
        snapshots, audit = replay_events(
            {"WRK"},
            [{
                "event_type": "IDENTITY_CHANGE",
                "corporate_effective_date": "2024-07-05",
                "trading_start_date": "2024-07-08",
                "index_effective_date": "2024-07-08",
                "effective_date": "2024-07-08",
                "action": "RENAME",
                "old_ticker": "WRK",
                "ticker": "SW",
                "event_status": "VERIFIED_CORPORATE_CONTINUITY",
            }],
            minimum_size=1,
            maximum_size=1,
        )
        self.assertEqual("2024-07-08", snapshots[0]["effective_date"])
        self.assertTrue(audit["replay_complete"])

    def test_replays_corporate_succession_atomically(self):
        snapshots, audit = replay_events(
            {"MYL", "AAA"},
            [{
                "event_type": "CORPORATE_SUCCESSION",
                "corporate_effective_date": "2020-11-16",
                "trading_start_date": "2020-11-17",
                "index_effective_date": "2020-11-17",
                "effective_date": "2020-11-17",
                "action": "SUCCESSION",
                "old_ticker": "MYL",
                "ticker": "VTRS",
                "event_status": "VERIFIED_CORPORATE_CONTINUITY",
            }],
            minimum_size=1,
            maximum_size=2,
        )
        self.assertEqual(["VTRS"], snapshots[0]["added"])
        self.assertEqual(["MYL"], snapshots[0]["removed"])
        self.assertEqual(0, audit["errors"])
        self.assertTrue(audit["replay_complete"])

    def test_replays_multi_class_identity_consolidation(self):
        snapshots, audit = replay_events(
            {"DISCA", "DISCK", "AAA"},
            [{
                "event_type": "IDENTITY_CHANGE",
                "effective_date": "2022-04-11",
                "action": "RENAME",
                "old_ticker": "DISCA|DISCK",
                "ticker": "WBD",
                "event_status": "VERIFIED_CORPORATE_CONTINUITY",
            }],
            minimum_size=1,
            maximum_size=3,
        )
        self.assertEqual(["WBD"], snapshots[0]["added"])
        self.assertEqual(["DISCA", "DISCK"], snapshots[0]["removed"])
        self.assertEqual(2, audit["final_count"])
        self.assertTrue(audit["replay_complete"])

    def test_applies_disclosed_diagnostic_baseline_correction(self):
        corrected, audit = apply_baseline_corrections(
            {"AAA"},
            [{
                "as_of": "2016-07-18",
                "entity_id": "HCP_LEGACY",
                "cik": "0000765880",
                "ticker": "HCP",
                "correction_type": "RESTORE_MISSING_HISTORICAL_SECURITY",
                "action": "ADD",
                "event_status": "VERIFIED_BASELINE_CONTINUITY_BACKCAST",
                "inference": "true",
                "promotion_scope": "DIAGNOSTIC_BASELINE_ONLY",
            }],
            as_of=date(2016, 7, 18),
        )
        self.assertEqual({"AAA", "HCP"}, corrected)
        self.assertEqual(1, audit["baseline_corrections"])
        self.assertEqual(
            "DIAGNOSTIC_BASELINE_ONLY",
            audit["baseline_correction_scope"],
        )

    def test_rejects_baseline_correction_as_official_promotion(self):
        with self.assertRaises(ConstituentReplayError):
            apply_baseline_corrections(
                {"AAA"},
                [{
                    "as_of": "2016-07-18",
                    "entity_id": "HCP_LEGACY",
                    "cik": "0000765880",
                    "ticker": "HCP",
                    "correction_type": "RESTORE_MISSING_HISTORICAL_SECURITY",
                    "action": "ADD",
                    "event_status": "VERIFIED_BASELINE_CONTINUITY_BACKCAST",
                    "inference": "true",
                    "promotion_scope": "OFFICIAL",
                }],
                as_of=date(2016, 7, 18),
            )


if __name__ == "__main__":
    unittest.main()
