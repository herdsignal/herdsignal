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

    def test_excludes_audited_zero_effect_source_artifact(self):
        reconciliation = [{
            "candidate_effective_date": "2023-05-09",
            "resolved_effective_date": "",
            "action": "ADD",
            "ticker": "BRK.B",
            "status": "NO_OFFICIAL_DOCUMENT_MATCH",
        }]
        anomalies = [{
            "candidate_effective_date": "2023-05-09",
            "action": "ADD",
            "ticker": "BRK.B",
            "exclude_from_official_ledger": True,
        }]

        rows, audit = build_integrated_ledger(
            reconciliation, [], [], [], [],
            reconstruction_anomalies=anomalies,
        )

        self.assertEqual([], rows)
        self.assertEqual(1, audit["quarantined_source_artifacts"])

    def test_replaces_continuity_components_with_verified_events(self):
        reconciliation = [
            {
                "candidate_effective_date": "2019-11-05",
                "resolved_effective_date": "2019-11-05",
                "action": "ADD",
                "ticker": "NEW",
                "status": "VERIFIED_CORPORATE_CONTINUITY_COMPONENT",
            }
        ]
        continuity = [{
            "event_type": "SAME_CIK_RENAME",
            "candidate_effective_date": "2019-11-05",
            "effective_date": "2019-11-05",
            "ticker": "NEW",
            "old_ticker": "OLD",
            "cik": "0000000001",
            "sp_source_url": "",
            "sp_source_sha256": "",
            "sec_source_url": "https://www.sec.gov/example",
            "sec_source_sha256": "a" * 64,
        }]

        rows, audit = build_integrated_ledger(
            reconciliation, [], [], [], [], continuity_events=continuity
        )

        self.assertEqual(1, len(rows))
        self.assertEqual("IDENTITY_CHANGE", rows[0]["event_type"])
        self.assertEqual("VERIFIED_CORPORATE_CONTINUITY", rows[0]["event_status"])
        self.assertEqual(1, audit["corporate_continuity_events"])
        self.assertTrue(audit["replay_ready"])

    def test_maps_same_cik_membership_continuity_to_identity_change(self):
        reconciliation = [
            {
                "candidate_effective_date": "2022-04-11",
                "resolved_effective_date": "2022-04-11",
                "action": action,
                "ticker": ticker,
                "status": "VERIFIED_CORPORATE_CONTINUITY_COMPONENT",
            }
            for action, ticker in (
                ("REMOVE", "DISCA"),
                ("REMOVE", "DISCK"),
                ("ADD", "WBD"),
            )
        ]
        continuity = [{
            "event_type": "SAME_CIK_MEMBERSHIP_CONTINUITY",
            "candidate_effective_date": "2022-04-11",
            "effective_date": "2022-04-11",
            "ticker": "WBD",
            "old_ticker": "DISCA|DISCK",
            "cik": "0001437107",
            "sp_source_url": "https://press.spglobal.com/example",
            "sp_source_sha256": "a" * 64,
            "sec_source_url": "https://www.sec.gov/example",
            "sec_source_sha256": "b" * 64,
        }]
        rows, _ = build_integrated_ledger(
            reconciliation, [], [], [], [], continuity_events=continuity
        )
        self.assertEqual(1, len(rows))
        self.assertEqual("IDENTITY_CHANGE", rows[0]["event_type"])
        self.assertEqual("DISCA|DISCK", rows[0]["old_ticker"])

    def test_maps_spinoff_ticker_reuse_to_addition(self):
        reconciliation = [{
            "candidate_effective_date": "2020-03-03",
            "resolved_effective_date": "2020-03-03",
            "action": "ADD",
            "ticker": "TT",
            "status": "VERIFIED_CORPORATE_CONTINUITY_COMPONENT",
        }]
        continuity = [{
            "event_type": "SPINOFF_DUAL_MEMBERSHIP_ADDITION",
            "candidate_effective_date": "2020-03-03",
            "effective_date": "2020-03-03",
            "ticker": "TT",
            "old_ticker": "IR",
            "cik": "0001466258",
            "sp_source_url": "https://press.spglobal.com/example",
            "sp_source_sha256": "a" * 64,
            "sec_source_url": "https://www.sec.gov/example",
            "sec_source_sha256": "b" * 64,
        }]
        rows, _ = build_integrated_ledger(
            reconciliation, [], [], [], [], continuity_events=continuity
        )
        self.assertEqual("MEMBERSHIP_CHANGE", rows[0]["event_type"])
        self.assertEqual("ADD", rows[0]["action"])
        self.assertEqual(
            "S_AND_P_SPINOFF_DUAL_MEMBERSHIP",
            rows[0]["corporate_action_evidence"],
        )


if __name__ == "__main__":
    unittest.main()
