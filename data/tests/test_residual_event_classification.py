import unittest

from herd.residual_event_classification import (
    ACTUAL_MEMBERSHIP_CHANGE,
    MISSING_OFFICIAL_DOCUMENT,
    RECONSTRUCTION_ANOMALY,
    UNCONFIRMED_IDENTITY_CHANGE,
    classify_residual_events,
)


class ResidualEventClassificationTest(unittest.TestCase):
    def test_separates_four_fail_closed_resolution_categories(self):
        reconciliation = [
            {"candidate_effective_date": "2020-01-02", "action": "ADD",
             "ticker": "NEW", "status": "NO_OFFICIAL_DOCUMENT_MATCH"},
            {"candidate_effective_date": "2020-01-02", "action": "REMOVE",
             "ticker": "OLD", "status": "NO_OFFICIAL_DOCUMENT_MATCH"},
            {"candidate_effective_date": "2020-02-03", "action": "ADD",
             "ticker": "AAA", "status": "OFFICIAL_DOCUMENT_TICKER_ONLY"},
            {"candidate_effective_date": "2020-03-01", "action": "REMOVE",
             "ticker": "BRK.B", "status": "NO_OFFICIAL_DOCUMENT_MATCH"},
            {"candidate_effective_date": "2020-03-02", "action": "ADD",
             "ticker": "BRK-B", "status": "NO_OFFICIAL_DOCUMENT_MATCH"},
            {"candidate_effective_date": "2020-04-01", "action": "ADD",
             "ticker": "MISS", "status": "NO_OFFICIAL_DOCUMENT_MATCH"},
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
        self.assertEqual(MISSING_OFFICIAL_DOCUMENT, categories["MISS"])
        self.assertEqual(0, audit["promotion_allowed_events"])
        self.assertFalse(audit["survivorship_safe"])

    def test_does_not_reclassify_verified_identity_components(self):
        rows, audit = classify_residual_events([{
            "candidate_effective_date": "2020-01-02", "action": "ADD",
            "ticker": "NEW", "status": "VERIFIED_IDENTITY_CHANGE_COMPONENT",
        }], [])

        self.assertEqual([], rows)
        self.assertEqual(0, audit["residual_events"])


if __name__ == "__main__":
    unittest.main()
