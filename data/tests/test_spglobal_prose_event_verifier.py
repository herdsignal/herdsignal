import unittest

from herd.spglobal_prose_event_verifier import verify_candidate


class SpglobalProseEventVerifierTest(unittest.TestCase):
    def test_verifies_add_and_remove_with_same_qualified_date(self):
        release = {
            "published_date": "2019-09-20",
            "source_url": "https://press.spglobal.com/example",
            "source_sha256": "a" * 64,
            "text": (
                "The following changes are effective prior to the open of trading on "
                "Thursday, September 26, 2019: NVR Inc. (NYSE: NVR) will replace "
                "Jefferies Financial Group Inc. (NYSE: JEF) in the S&P 500."
            ),
        }
        add = verify_candidate(
            {"effective_date": "2019-09-26", "action": "ADD", "ticker": "NVR"},
            release,
        )
        remove = verify_candidate(
            {"effective_date": "2019-09-26", "action": "REMOVE", "ticker": "JEF"},
            release,
        )
        self.assertEqual("SEMANTICS_AND_DATE_VERIFIED", add["verification_status"])
        self.assertEqual("SEMANTICS_AND_DATE_VERIFIED", remove["verification_status"])

    def test_does_not_confirm_date_mentioned_without_effective_qualifier(self):
        release = {
            "published_date": "2019-09-20",
            "source_url": "https://press.spglobal.com/example",
            "source_sha256": "a" * 64,
            "text": (
                "On September 26, 2019 NVR Inc. (NYSE: NVR) will replace "
                "Jefferies Financial Group in the S&P 500."
            ),
        }
        result = verify_candidate(
            {"effective_date": "2019-09-26", "action": "ADD", "ticker": "NVR"},
            release,
        )
        self.assertEqual("PROSE_NOT_CONFIRMED", result["verification_status"])

    def test_does_not_confirm_wrong_action(self):
        release = {
            "published_date": "2019-09-20",
            "source_url": "https://press.spglobal.com/example",
            "source_sha256": "a" * 64,
            "text": (
                "Effective September 26, 2019 NVR Inc. (NYSE: NVR) will replace "
                "Jefferies Financial Group in the S&P 500."
            ),
        }
        result = verify_candidate(
            {"effective_date": "2019-09-26", "action": "REMOVE", "ticker": "NVR"},
            release,
        )
        self.assertEqual("PROSE_NOT_CONFIRMED", result["verification_status"])


if __name__ == "__main__":
    unittest.main()
