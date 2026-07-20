import unittest

from herd.residual_event_classification import (
    ACTUAL_MEMBERSHIP_CHANGE,
    CORPORATE_ACTION_CHAIN_REQUIRED,
    EVIDENCE_TRIAGE_REQUIRED,
    RECONSTRUCTION_ANOMALY,
    SHARE_CLASS_REQUIRED,
    TICKER_ALIAS_REQUIRED,
    UNCONFIRMED_IDENTITY_CHANGE,
    classify_residual_events,
)


class ResidualEventClassificationTest(unittest.TestCase):
    def test_separates_four_fail_closed_resolution_categories(self):
        reconciliation = [
            {"candidate_effective_date": "2020-01-02", "action": "ADD",
             "ticker": "NEW", "status": "UNMATCHED_REQUIRES_CORPORATE_ACTION_CHAIN"},
            {"candidate_effective_date": "2020-01-02", "action": "REMOVE",
             "ticker": "OLD", "status": "UNMATCHED_REQUIRES_CORPORATE_ACTION_CHAIN"},
            {"candidate_effective_date": "2020-02-03", "action": "ADD",
             "ticker": "AAA", "status": "OFFICIAL_DOCUMENT_TICKER_ONLY"},
            {"candidate_effective_date": "2020-03-01", "action": "REMOVE",
             "ticker": "BRK.B", "status": "UNMATCHED_RECONSTRUCTION_ANOMALY"},
            {"candidate_effective_date": "2020-03-02", "action": "ADD",
             "ticker": "BRK-B", "status": "UNMATCHED_RECONSTRUCTION_ANOMALY"},
            {"candidate_effective_date": "2020-04-01", "action": "ADD",
             "ticker": "MISS", "status": "UNMATCHED_REQUIRES_EVIDENCE_TRIAGE"},
            {"candidate_effective_date": "2020-05-01", "action": "REMOVE",
             "ticker": "UAA", "status": "UNMATCHED_REQUIRES_SHARE_CLASS_NORMALIZATION"},
            {"candidate_effective_date": "2020-06-01", "action": "ADD",
             "ticker": "IQV", "status": "UNMATCHED_REQUIRES_TICKER_ALIAS"},
        ]
        identity = [{
            "old_candidate_date": "2020-01-02", "new_candidate_date": "2020-01-02",
            "old_ticker": "OLD", "new_ticker": "NEW",
            "identity_status": "SEC_SAME_CIK_IDENTITY_DATE_UNVERIFIED",
        }]

        rows, audit = classify_residual_events(reconciliation, identity)
        categories = {row["ticker"]: row["residual_category"] for row in rows}

        self.assertEqual(UNCONFIRMED_IDENTITY_CHANGE, categories["OLD"])
        self.assertEqual(UNCONFIRMED_IDENTITY_CHANGE, categories["NEW"])
        self.assertEqual(ACTUAL_MEMBERSHIP_CHANGE, categories["AAA"])
        self.assertEqual(RECONSTRUCTION_ANOMALY, categories["BRK.B"])
        self.assertEqual(RECONSTRUCTION_ANOMALY, categories["BRK-B"])
        self.assertEqual(EVIDENCE_TRIAGE_REQUIRED, categories["MISS"])
        self.assertEqual(SHARE_CLASS_REQUIRED, categories["UAA"])
        self.assertEqual(TICKER_ALIAS_REQUIRED, categories["IQV"])
        self.assertEqual(0, audit["promotion_allowed_events"])
        self.assertFalse(audit["survivorship_safe"])

    def test_does_not_reclassify_verified_identity_components(self):
        for status in (
            "VERIFIED_IDENTITY_CHANGE_COMPONENT",
            "VERIFIED_CORPORATE_CONTINUITY_COMPONENT",
        ):
            rows, audit = classify_residual_events([{
                "candidate_effective_date": "2020-01-02", "action": "ADD",
                "ticker": "NEW", "status": status,
            }], [])

            self.assertEqual([], rows)
            self.assertEqual(0, audit["residual_events"])


if __name__ == "__main__":
    unittest.main()
