import unittest

from herd.sec_merger_evidence import classify_merger_document


class SecMergerEvidenceTest(unittest.TestCase):
    def test_detects_completed_merger_and_delisting(self):
        result = classify_merger_document(
            b"The Company completed the merger and requested removal from listing on Form 25."
        )
        self.assertEqual(
            "MERGER_COMPLETION_AND_DELISTING_EVIDENCE",
            result["classification_status"],
        )
        self.assertTrue(result["requires_review"])

    def test_agreement_is_not_misclassified_as_completed(self):
        result = classify_merger_document(b"Agreement and Plan of Merger")
        self.assertEqual("MERGER_AGREEMENT_EVIDENCE", result["classification_status"])

    def test_unrelated_8k_has_no_strong_evidence(self):
        result = classify_merger_document(b"Quarterly investor presentation")
        self.assertEqual("NO_STRONG_MERGER_EVIDENCE", result["classification_status"])


if __name__ == "__main__":
    unittest.main()
