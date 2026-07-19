import unittest

from herd.official_candidate_reconciliation import reconcile_candidates


class OfficialCandidateReconciliationTest(unittest.TestCase):
    def test_prefers_exact_table_and_corrects_nearby_candidate_date(self):
        candidates = [
            {"effective_date": "2020-10-09", "action": "ADD", "ticker": "VNT"},
            {"effective_date": "2020-10-12", "action": "REMOVE", "ticker": "NBL"},
        ]
        table = [
            {
                "effective_date": "2020-10-09", "action": "ADD", "ticker": "VNT",
                "announcement_date": "2020-10-05", "company_name": "Vontier",
                "source_url": "https://press.spglobal.com/a", "source_sha256": "a" * 64,
            },
            {
                "effective_date": "2020-10-09", "action": "REMOVE", "ticker": "NBL",
                "announcement_date": "2020-10-05", "company_name": "Noble",
                "source_url": "https://press.spglobal.com/a", "source_sha256": "a" * 64,
            },
        ]
        rows, audit = reconcile_candidates(candidates, table, [], [])
        self.assertEqual("OFFICIAL_TABLE_EXACT", rows[0]["status"])
        self.assertEqual(
            "CANDIDATE_DATE_CORRECTED_BY_OFFICIAL_TABLE", rows[1]["status"]
        )
        self.assertEqual("2020-10-09", rows[1]["resolved_effective_date"])
        self.assertEqual(2, audit["resolved_events"])

    def test_does_not_merge_distant_same_ticker_event(self):
        candidates = [{"effective_date": "2023-05-17", "action": "ADD", "ticker": "CEG"}]
        table = [{"effective_date": "2022-02-02", "action": "ADD", "ticker": "CEG"}]
        rows, audit = reconcile_candidates(candidates, table, [], [])
        self.assertEqual(
            "DISTANT_SAME_TICKER_EVENT_REQUIRES_IDENTITY_REVIEW", rows[0]["status"]
        )
        self.assertFalse(audit["complete"])


if __name__ == "__main__":
    unittest.main()
