import unittest

from herd.integrated_event_ledger import build_integrated_ledger


class IntegratedEventLedgerTest(unittest.TestCase):
    def test_combines_official_event_cik_and_common_form25_without_overclaim(self):
        reconciliation = [{
            "candidate_effective_date": "2024-01-10",
            "resolved_effective_date": "2024-01-09",
            "action": "REMOVE", "ticker": "EX", "company_name": "Example",
            "status": "CANDIDATE_DATE_CORRECTED_BY_OFFICIAL_TABLE",
            "source_url": "https://press.spglobal.com/a", "source_sha256": "a" * 64,
        }]
        cik = [{
            "effective_date": "2024-01-09", "action": "REMOVE", "ticker": "EX",
            "cik": "0000000001", "cik_link_status": "UNIQUE_CIK_NAME_CANDIDATE",
        }]
        candidates = [{
            "effective_date": "2024-01-09", "ticker": "EX",
            "filing_url": "https://www.sec.gov/a",
        }]
        classification = [{
            "filing_url": "https://www.sec.gov/a",
            "classification_status": "COMMON_EQUITY_FORM25_EVIDENCE",
        }]
        rows, audit = build_integrated_ledger(
            reconciliation, cik, candidates, classification, []
        )
        self.assertEqual(
            "OFFICIAL_EVENT_WITH_SEC_ACTION_EVIDENCE", rows[0]["event_status"]
        )
        self.assertEqual("REQUIRES_HUMAN_REVIEW", rows[0]["review_status"])
        self.assertTrue(audit["replay_ready"])
        self.assertFalse(audit["survivorship_safe"])

    def test_unresolved_candidate_blocks_replay(self):
        reconciliation = [{
            "candidate_effective_date": "2024-01-10",
            "resolved_effective_date": "", "action": "ADD", "ticker": "EX",
            "company_name": "", "status": "NO_OFFICIAL_DOCUMENT_MATCH",
            "source_url": "", "source_sha256": "",
        }]
        rows, audit = build_integrated_ledger(reconciliation, [], [], [], [])
        self.assertEqual("UNRESOLVED", rows[0]["event_status"])
        self.assertFalse(audit["replay_ready"])
        self.assertFalse(audit["survivorship_safe"])

    def test_collapses_identity_components_into_one_transition(self):
        reconciliation = [
            {
                "candidate_effective_date": "2022-06-09",
                "resolved_effective_date": "2022-06-09",
                "action": action,
                "ticker": ticker,
                "status": "VERIFIED_IDENTITY_CHANGE_COMPONENT",
            }
            for action, ticker in (("REMOVE", "FB"), ("ADD", "META"))
        ]
        transitions = [{
            "effective_date": "2022-06-09",
            "old_candidate_date": "2022-06-09",
            "new_candidate_date": "2022-06-09",
            "old_ticker": "FB",
            "new_ticker": "META",
            "cik": "0001326801",
        }]
        rows, audit = build_integrated_ledger(
            reconciliation, [], [], [], [], transitions
        )
        self.assertEqual(1, len(rows))
        self.assertEqual("IDENTITY_CHANGE", rows[0]["event_type"])
        self.assertEqual("VERIFIED_IDENTITY_CHANGE", rows[0]["event_status"])
        self.assertTrue(audit["replay_ready"])


if __name__ == "__main__":
    unittest.main()
