import unittest

from herd.sec_identity_evidence_merge import merge_identity_evidence


class SecIdentityEvidenceMergeTest(unittest.TestCase):
    def test_prefers_later_verified_evidence_for_same_pair(self):
        base = {
            "candidate_cik": "1",
            "old_candidate_date": "2020-01-02",
            "new_candidate_date": "2020-01-02",
            "old_ticker": "OLD",
            "new_ticker": "NEW",
        }
        old = [{
            **base,
            "identity_status": "SEC_SAME_CIK_IDENTITY_DATE_UNVERIFIED",
            "resolved_effective_date": "",
        }]
        new = [{
            **base,
            "identity_status": "SEC_IDENTITY_AND_EFFECTIVE_DATE_VERIFIED",
            "resolved_effective_date": "2020-01-02",
        }]

        rows, audit = merge_identity_evidence([old, new])

        self.assertEqual(1, len(rows))
        self.assertEqual(
            "SEC_IDENTITY_AND_EFFECTIVE_DATE_VERIFIED",
            rows[0]["identity_status"],
        )
        self.assertEqual(1, audit["verified_identity_pairs"])


if __name__ == "__main__":
    unittest.main()
