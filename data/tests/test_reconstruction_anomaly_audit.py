import unittest

from herd.reconstruction_anomaly_audit import audit_reconstruction_anomalies


class ReconstructionAnomalyAuditTest(unittest.TestCase):
    def test_quarantines_zero_net_format_oscillation(self):
        rows = [
            {
                "candidate_effective_date": "2023-05-09",
                "action": "REMOVE",
                "ticker": "BRK-B",
                "residual_category": "PUBLIC_RECONSTRUCTION_ANOMALY",
                "reconciliation_status": "NO_OFFICIAL_DOCUMENT_MATCH",
            },
            {
                "candidate_effective_date": "2023-05-09",
                "action": "ADD",
                "ticker": "BRK.B",
                "residual_category": "PUBLIC_RECONSTRUCTION_ANOMALY",
                "reconciliation_status": "NO_OFFICIAL_DOCUMENT_MATCH",
            },
        ]

        audited, result = audit_reconstruction_anomalies(rows, [])

        self.assertTrue(all(
            row["exclude_from_official_ledger"] for row in audited
        ))
        self.assertEqual(0, result["composition_effect_of_quarantine"])

    def test_keeps_unbalanced_loop_open(self):
        rows = [{
            "candidate_effective_date": "2023-05-09",
            "action": "ADD",
            "ticker": "AAA",
            "residual_category": "PUBLIC_RECONSTRUCTION_ANOMALY",
            "reconciliation_status": "NO_OFFICIAL_DOCUMENT_MATCH",
        }]

        audited, result = audit_reconstruction_anomalies(rows, [])

        self.assertFalse(audited[0]["exclude_from_official_ledger"])
        self.assertEqual(1, result["open_review_rows"])


if __name__ == "__main__":
    unittest.main()
