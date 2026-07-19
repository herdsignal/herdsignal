import unittest

from herd.unresolved_event_audit import (
    UnresolvedEventAuditError,
    audit_unresolved_events,
)


class UnresolvedEventAuditTest(unittest.TestCase):
    def test_classifies_resolution_lane_without_using_sec_as_membership_proof(self):
        reconciliation = [
            {
                "candidate_effective_date": "2024-01-08",
                "action": "ADD",
                "ticker": "AAA",
                "status": "OFFICIAL_DOCUMENT_TICKER_ONLY",
            },
            {
                "candidate_effective_date": "2024-01-08",
                "action": "REMOVE",
                "ticker": "BBB",
                "status": "NO_OFFICIAL_DOCUMENT_MATCH",
            },
        ]
        suggestions = [{
            "effective_date": "2024-01-08",
            "action": "ADD",
            "ticker": "AAA",
        }]

        rows, audit = audit_unresolved_events(reconciliation, suggestions)

        self.assertEqual(2, audit["pending_events"])
        self.assertEqual(1, audit["events_with_document_candidates"])
        self.assertEqual(
            "OFFICIAL_PROSE_OR_TABLE_EXTRACTION", rows[0]["resolution_lane"]
        )
        self.assertEqual("IDENTITY_OR_CAUSE_ONLY", rows[0]["sec_evidence_role"])
        self.assertFalse(rows[0]["same_date_action_imbalance"])

    def test_marks_weekend_and_same_date_imbalance(self):
        rows, audit = audit_unresolved_events([{
            "candidate_effective_date": "2024-01-06",
            "action": "ADD",
            "ticker": "AAA",
            "status": "NO_OFFICIAL_DOCUMENT_MATCH",
        }], [])

        self.assertTrue(rows[0]["candidate_date_is_weekend"])
        self.assertTrue(rows[0]["same_date_action_imbalance"])
        self.assertEqual(1, audit["weekend_candidate_dates"])

    def test_rejects_unknown_status_instead_of_silently_accepting_it(self):
        with self.assertRaises(UnresolvedEventAuditError):
            audit_unresolved_events([{
                "candidate_effective_date": "2024-01-08",
                "action": "ADD",
                "ticker": "AAA",
                "status": "NEW_UNKNOWN_STATUS",
            }], [])


if __name__ == "__main__":
    unittest.main()
