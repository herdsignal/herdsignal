import unittest

from herd.sec_form25_classifier import classify_form25


class SecForm25ClassifierTest(unittest.TestCase):
    def test_identifies_common_equity_without_claiming_final_confirmation(self):
        result = classify_form25(b"<securityDescription>Class A Common Stock</securityDescription>")
        self.assertEqual("COMMON_EQUITY_FORM25_EVIDENCE", result["status"])
        self.assertTrue(result["requires_review"])

    def test_separates_debt_security(self):
        result = classify_form25(b"<securityDescription>5.5% Notes due 2030</securityDescription>")
        self.assertEqual("OTHER_SECURITY_FORM25", result["status"])

    def test_identifies_common_equity_inside_mixed_security_document(self):
        result = classify_form25(b"Common Stock and Warrants")
        self.assertEqual(
            "COMMON_EQUITY_INCLUDED_WITH_OTHER_SECURITIES", result["status"]
        )


if __name__ == "__main__":
    unittest.main()
