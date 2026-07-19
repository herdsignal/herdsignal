import unittest

from herd.spglobal_prose_event_verifier import (
    canonical_verified_events,
    verify_candidate,
)


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

    def test_maps_after_close_to_following_candidate_session(self):
        release = {
            "published_date": "2016-08-31",
            "source_url": "https://press.spglobal.com/example",
            "source_sha256": "a" * 64,
            "text": (
                "Charter Communications Inc. (NASD: CHTR) will replace EMC Corp. "
                "(NYSE: EMC) in the S&P 500 after the close of trading on "
                "Wednesday, September 7."
            ),
        }
        result = verify_candidate(
            {"effective_date": "2016-09-08", "action": "ADD", "ticker": "CHTR"},
            release,
        )
        self.assertEqual("SEMANTICS_AND_DATE_VERIFIED", result["verification_status"])
        self.assertEqual("2016-09-07", result["stated_effective_date"])
        self.assertEqual("AFTER_CLOSE", result["effective_timing"])
        self.assertEqual("2016-09-08", result["membership_session_date"])

    def test_infers_next_year_for_yearless_january_date(self):
        release = {
            "published_date": "2018-12-27",
            "source_url": "https://press.spglobal.com/example",
            "source_sha256": "a" * 64,
            "text": (
                "First Republic Bank (NYSE: FRC) will replace SCANA "
                "(NYSE: SCG) in the S&P 500 effective prior to the open on "
                "Wednesday, January 2."
            ),
        }
        result = verify_candidate(
            {"effective_date": "2019-01-02", "action": "ADD", "ticker": "FRC"},
            release,
        )
        self.assertEqual("SEMANTICS_AND_DATE_VERIFIED", result["verification_status"])
        self.assertEqual("2019-01-02", result["stated_effective_date"])

    def test_does_not_treat_merger_completion_date_as_index_effective_date(self):
        release = {
            "published_date": "2016-11-29",
            "source_url": "https://press.spglobal.com/example",
            "source_sha256": "a" * 64,
            "text": (
                "AmSurg will replace Legg Mason in the S&P 500. AmSurg is "
                "acquiring Envision Healthcare Holdings Inc. (NYSE: EVHC) in "
                "a transaction expected to be completed on December 1."
            ),
        }
        result = verify_candidate(
            {"effective_date": "2016-12-02", "action": "ADD", "ticker": "EVHC"},
            release,
        )
        self.assertEqual("PROSE_NOT_CONFIRMED", result["verification_status"])

    def test_canonicalizes_repeated_release_to_first_identical_announcement(self):
        base = {
            "effective_date": "2020-12-21",
            "stated_effective_date": "2020-12-21",
            "effective_timing": "PRIOR_TO_OPEN",
            "action": "ADD",
            "ticker": "TSLA",
            "verification_status": "SEMANTICS_AND_DATE_VERIFIED",
        }
        rows, conflicts = canonical_verified_events([
            {**base, "announcement_date": "2020-12-11", "source_url": "second"},
            {**base, "announcement_date": "2020-11-16", "source_url": "first"},
        ])
        self.assertEqual([], conflicts)
        self.assertEqual("first", rows[0]["source_url"])

    def test_rejects_repeated_release_with_conflicting_effective_semantics(self):
        base = {
            "effective_date": "2020-12-21",
            "stated_effective_date": "2020-12-21",
            "action": "ADD",
            "ticker": "TSLA",
            "verification_status": "SEMANTICS_AND_DATE_VERIFIED",
            "announcement_date": "2020-11-16",
        }
        rows, conflicts = canonical_verified_events([
            {**base, "effective_timing": "PRIOR_TO_OPEN", "source_url": "first"},
            {**base, "effective_timing": "AFTER_CLOSE", "source_url": "second"},
        ])
        self.assertEqual([], rows)
        self.assertEqual(
            "CONFLICTING_OFFICIAL_EFFECTIVE_SEMANTICS", conflicts[0]["reason"]
        )


if __name__ == "__main__":
    unittest.main()
