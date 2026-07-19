import unittest

from herd.identity_transition_reconciliation import reconcile_identity_transitions


class IdentityTransitionReconciliationTest(unittest.TestCase):
    def test_reclassifies_verified_pair_without_marking_dataset_safe(self):
        reconciliation = [
            {
                "candidate_effective_date": "2022-06-09",
                "action": "REMOVE", "ticker": "FB",
                "status": "NO_OFFICIAL_DOCUMENT_MATCH",
                "resolved_effective_date": "",
            },
            {
                "candidate_effective_date": "2022-06-09",
                "action": "ADD", "ticker": "META",
                "status": "NO_OFFICIAL_DOCUMENT_MATCH",
                "resolved_effective_date": "",
            },
        ]
        evidence = [{
            "candidate_cik": "0001326801",
            "old_ticker": "FB", "new_ticker": "META",
            "old_candidate_date": "2022-06-09",
            "new_candidate_date": "2022-06-09",
            "resolved_effective_date": "2022-06-09",
            "identity_status": "SEC_IDENTITY_AND_EFFECTIVE_DATE_VERIFIED",
            "evidence_accessions": "a|b",
        }]
        rows, transitions, audit = reconcile_identity_transitions(
            reconciliation, evidence
        )
        self.assertEqual(1, len(transitions))
        self.assertTrue(all(
            row["status"] == "VERIFIED_IDENTITY_CHANGE_COMPONENT" for row in rows
        ))
        self.assertEqual(0, audit["remaining_non_official_rows"])
        self.assertFalse(audit["survivorship_safe"])

    def test_deduplicates_same_transition_candidates(self):
        reconciliation = [
            {
                "candidate_effective_date": value,
                "action": action, "ticker": ticker,
                "status": "NO_OFFICIAL_DOCUMENT_MATCH",
                "resolved_effective_date": "",
            }
            for value, action, ticker in [
                ("2023-08-31", "REMOVE", "ABC"),
                ("2023-09-02", "REMOVE", "ABC"),
                ("2023-09-03", "ADD", "COR"),
            ]
        ]
        evidence = [
            {
                "candidate_cik": "0001140859",
                "old_ticker": "ABC", "new_ticker": "COR",
                "old_candidate_date": old_date,
                "new_candidate_date": "2023-09-03",
                "resolved_effective_date": "2023-08-30",
                "identity_status": "SEC_IDENTITY_AND_EFFECTIVE_DATE_VERIFIED",
                "evidence_accessions": "a",
            }
            for old_date in ("2023-08-31", "2023-09-02")
        ]
        rows, transitions, audit = reconcile_identity_transitions(
            reconciliation, evidence
        )
        self.assertEqual(1, len(transitions))
        self.assertEqual(2, audit["reclassified_candidate_rows"])
        self.assertEqual(1, audit["remaining_non_official_rows"])

    def test_defers_many_old_symbols_converging_to_one_new_symbol(self):
        reconciliation = [
            {
                "candidate_effective_date": "2022-04-11",
                "action": "REMOVE",
                "ticker": ticker,
                "status": "NO_OFFICIAL_DOCUMENT_MATCH",
            }
            for ticker in ("DISCA", "DISCK")
        ] + [{
            "candidate_effective_date": "2022-04-11",
            "action": "ADD",
            "ticker": "WBD",
            "status": "NO_OFFICIAL_DOCUMENT_MATCH",
        }]
        evidence = [
            {
                "candidate_cik": "1437107",
                "old_candidate_date": "2022-04-11",
                "new_candidate_date": "2022-04-11",
                "old_ticker": ticker,
                "new_ticker": "WBD",
                "resolved_effective_date": "2022-04-11",
                "identity_status": "SEC_IDENTITY_AND_EFFECTIVE_DATE_VERIFIED",
            }
            for ticker in ("DISCA", "DISCK")
        ]

        updated, transitions, audit = reconcile_identity_transitions(
            reconciliation, evidence
        )

        self.assertEqual([], transitions)
        self.assertTrue(all(
            row["status"] == "NO_OFFICIAL_DOCUMENT_MATCH" for row in updated
        ))
        self.assertEqual(1, audit["complex_identity_groups_deferred"])


if __name__ == "__main__":
    unittest.main()
