import unittest

from herd.official_candidate_reconciliation import reconcile_candidates


class OfficialCandidateReconciliationTest(unittest.TestCase):
    def test_accepts_previous_reconciliation_as_candidate_input(self):
        rows, audit = reconcile_candidates(
            [{
                "candidate_effective_date": "2020-04-06",
                "action": "REMOVE",
                "ticker": "RTN",
            }],
            [],
            [{
                "effective_date": "2020-04-06",
                "action": "REMOVE",
                "ticker": "RTN",
            }],
            [],
        )
        self.assertEqual("OFFICIAL_PROSE_EXACT", rows[0]["status"])
        self.assertEqual(1, audit["resolved_events"])

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

    def test_applies_distant_date_only_from_reviewed_archived_table_claim(self):
        table = [{
            "effective_date": "2022-02-02", "action": "ADD", "ticker": "CEG",
            "announcement_date": "2022-01-26", "company_name": "Constellation Energy",
            "source_url": "https://press.spglobal.com/ceg",
            "source_sha256": "a" * 64,
        }]
        rows, audit = reconcile_candidates(
            [{"effective_date": "2023-05-17", "action": "ADD", "ticker": "CEG"}],
            table,
            [],
            [],
            reviewed_date_corrections=[{
                "candidate_effective_date": "2023-05-17",
                "action": "ADD",
                "ticker": "CEG",
                "corrected_effective_date": "2022-02-02",
                "source_url": "https://press.spglobal.com/ceg",
                "source_sha256": "a" * 64,
            }],
        )
        self.assertEqual(
            "CANDIDATE_DATE_CORRECTED_BY_REVIEWED_OFFICIAL_TABLE",
            rows[0]["status"],
        )
        self.assertEqual("2022-02-02", rows[0]["resolved_effective_date"])
        self.assertTrue(audit["complete"])

    def test_corrects_candidate_date_from_unambiguous_official_semantics(self):
        rows, audit = reconcile_candidates(
            [{"effective_date": "2017-07-25", "action": "REMOVE", "ticker": "RAI"}],
            [],
            [],
            [],
            [{
                "candidate_effective_date": "2017-07-25",
                "candidate_action": "REMOVE",
                "ticker": "RAI",
                "official_action": "REMOVE",
                "membership_session_date": "2017-07-26",
                "stated_effective_date": "2017-07-26",
                "effective_timing": "PRIOR_TO_OPEN",
                "announcement_date": "2017-07-19",
                "source_url": "https://press.spglobal.com/example",
                "source_sha256": "a" * 64,
                "extraction_status": "OFFICIAL_SEMANTICS_CONFLICTS_WITH_CANDIDATE",
            }],
        )
        self.assertEqual(
            "CANDIDATE_DATE_CORRECTED_BY_OFFICIAL_PROSE", rows[0]["status"]
        )
        self.assertEqual("2017-07-26", rows[0]["resolved_effective_date"])
        self.assertEqual(1, audit["resolved_events"])

    def test_keeps_action_conflict_open(self):
        rows, audit = reconcile_candidates(
            [{"effective_date": "2023-06-04", "action": "ADD", "ticker": "DISH"}],
            [],
            [],
            [],
            [{
                "candidate_effective_date": "2023-06-04",
                "candidate_action": "ADD",
                "ticker": "DISH",
                "official_action": "REMOVE",
                "membership_session_date": "2023-06-20",
                "stated_effective_date": "2023-06-20",
                "effective_timing": "PRIOR_TO_OPEN",
                "announcement_date": "2023-06-02",
                "source_url": "https://press.spglobal.com/example",
                "source_sha256": "a" * 64,
                "extraction_status": "OFFICIAL_SEMANTICS_CONFLICTS_WITH_CANDIDATE",
            }],
        )
        self.assertEqual(
            "CANDIDATE_ACTION_CONFLICTS_WITH_OFFICIAL_PROSE", rows[0]["status"]
        )
        self.assertEqual(0, audit["resolved_events"])

    def test_routes_unmatched_candidate_without_claiming_document_is_missing(self):
        rows, audit = reconcile_candidates(
            [{"effective_date": "2017-08-29", "action": "ADD", "ticker": "IQV"}],
            [],
            [],
            [],
            resolution_routes=[{
                "candidate_effective_date": "2017-08-29",
                "action": "ADD",
                "ticker": "IQV",
                "resolution_route": "TICKER_ALIAS",
            }],
        )
        self.assertEqual("UNMATCHED_REQUIRES_TICKER_ALIAS", rows[0]["status"])
        self.assertEqual("TICKER_ALIAS", rows[0]["resolution_route"])
        self.assertEqual(0, audit["resolved_events"])

    def test_marks_unknown_unmatched_candidate_for_triage(self):
        rows, _ = reconcile_candidates(
            [{"effective_date": "2020-01-02", "action": "ADD", "ticker": "NEW"}],
            [], [], [],
        )
        self.assertEqual("UNMATCHED_REQUIRES_EVIDENCE_TRIAGE", rows[0]["status"])


if __name__ == "__main__":
    unittest.main()
