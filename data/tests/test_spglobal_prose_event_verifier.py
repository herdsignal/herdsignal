import re
import unittest

from herd.spglobal_prose_event_verifier import (
    canonical_verified_events,
    classify_occurrence,
    verify_candidate,
)


class SpglobalProseEventVerifierTest(unittest.TestCase):
    def test_classifies_first_replacement_target_in_shared_removal_clause(self):
        text = (
            "Otis Worldwide Corp. (NYSE: OTIS) will replace Raytheon Co. "
            "(NYSE: RTN), and Carrier Global Corp. (NYSE: CARR) will replace "
            "Macy's Inc. (NYSE: M), both of which will be removed from the "
            "S&P 500 prior to the open of trading on Monday, April 6."
        )
        ticker_match = re.search(r"\(NYSE:\s*RTN\)", text)
        self.assertIsNotNone(ticker_match)
        self.assertEqual("REMOVE", classify_occurrence(text, ticker_match))

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

    def test_classifies_replaced_ticker_as_remove_before_later_addition_copy(self):
        release = {
            "published_date": "2017-03-06",
            "source_url": "https://press.spglobal.com/example",
            "source_sha256": "a" * 64,
            "text": (
                "DISH Network Corp. (NASD: DISH) will replace Linear Technology "
                "Corp. (NASD: LLTC) in the S&P 500 effective prior to the open "
                "on Monday, March 13. DISH will be added to the S&P 500 GICS "
                "Cable Sub-Industry index."
            ),
        }
        result = verify_candidate(
            {"effective_date": "2017-03-13", "action": "REMOVE", "ticker": "LLTC"},
            release,
        )
        self.assertEqual("SEMANTICS_AND_DATE_VERIFIED", result["verification_status"])

    def test_classifies_respectively_switch_groups(self):
        release = {
            "published_date": "2018-06-08",
            "source_url": "https://press.spglobal.com/example",
            "source_sha256": "a" * 64,
            "text": (
                "The changes will be effective prior to the open on Monday, "
                "June 18. HollyFrontier Corp. (NYSE: HFC) and Broadridge "
                "Financial Solutions Inc. (NYSE: BR) will switch places with "
                "Acuity Brands Inc. (NYSE: AYI) and Range Resources Corp. "
                "(NYSE: RRC) respectively in the S&P 500."
            ),
        }
        for action, ticker in (
            ("ADD", "HFC"), ("ADD", "BR"), ("REMOVE", "AYI"), ("REMOVE", "RRC"),
        ):
            with self.subTest(action=action, ticker=ticker):
                result = verify_candidate(
                    {"effective_date": "2018-06-18", "action": action, "ticker": ticker},
                    release,
                )
                self.assertEqual(
                    "SEMANTICS_AND_DATE_VERIFIED", result["verification_status"]
                )

    def test_classifies_move_and_switching_places_groups(self):
        release = {
            "published_date": "2019-12-13",
            "source_url": "https://press.spglobal.com/example",
            "source_sha256": "a" * 64,
            "text": (
                "The changes will be effective prior to the open on Monday, "
                "December 23. Live Nation (NYSE: LYV), Zebra (NASD: ZBRA), and "
                "STERIS (NYSE: STE) will move to the S&P 500, switching places "
                "with AMG (NYSE: AMG), TripAdvisor (NASD: TRIP), and Macerich "
                "(NYSE: MAC) respectively."
            ),
        }
        for action, ticker in (
            ("ADD", "LYV"), ("ADD", "ZBRA"), ("ADD", "STE"),
            ("REMOVE", "AMG"), ("REMOVE", "TRIP"), ("REMOVE", "MAC"),
        ):
            with self.subTest(action=action, ticker=ticker):
                result = verify_candidate(
                    {"effective_date": "2019-12-23", "action": action, "ticker": ticker},
                    release,
                )
                self.assertEqual(
                    "SEMANTICS_AND_DATE_VERIFIED", result["verification_status"]
                )

    def test_does_not_attach_previous_replacement_clause_to_next_ticker(self):
        release = {
            "published_date": "2016-08-31",
            "source_url": "https://press.spglobal.com/example",
            "source_sha256": "a" * 64,
            "text": (
                "Kraft Heinz (NASD: KHC) will replace EMC Corp. (NYSE: EMC) "
                "in the S&P 100, and Charter Communications (NASD: CHTR) will "
                "replace EMC in the S&P 500 after the close on September 7."
            ),
        }
        result = verify_candidate(
            {"effective_date": "2016-09-08", "action": "ADD", "ticker": "CHTR"},
            release,
        )
        self.assertEqual("SEMANTICS_AND_DATE_VERIFIED", result["verification_status"])

    def test_classifies_multiple_replacements_with_respectively(self):
        release = {
            "published_date": "2020-06-12",
            "source_url": "https://press.spglobal.com/example",
            "source_sha256": "a" * 64,
            "text": (
                "The changes are effective prior to the open on Monday, June 22. "
                "Tyler (NYSE: TYL), Bio-Rad (NYSE: BIO), and Teledyne "
                "(NYSE: TDY) will move to the S&P 500, replacing Harley-Davidson "
                "(NYSE: HOG), Nordstrom (NYSE: JWN), and Alliance Data "
                "(NYSE: ADS) respectively."
            ),
        }
        for ticker in ("HOG", "JWN", "ADS"):
            with self.subTest(ticker=ticker):
                result = verify_candidate(
                    {"effective_date": "2020-06-22", "action": "REMOVE", "ticker": ticker},
                    release,
                )
                self.assertEqual(
                    "SEMANTICS_AND_DATE_VERIFIED", result["verification_status"]
                )

    def test_accepts_nyse_american_exchange_label(self):
        release = {
            "published_date": "2024-01-02",
            "source_url": "https://press.spglobal.com/example",
            "source_sha256": "a" * 64,
            "text": (
                "Example Corp. (NYSE American: EX) will replace Old Corp. "
                "(NYSE MKT: OLD) in the S&P 500 effective prior to the open "
                "on Monday, January 8."
            ),
        }
        for action, ticker in (("ADD", "EX"), ("REMOVE", "OLD")):
            result = verify_candidate(
                {"effective_date": "2024-01-08", "action": action, "ticker": ticker},
                release,
            )
            self.assertEqual(
                "SEMANTICS_AND_DATE_VERIFIED", result["verification_status"]
            )

    def test_classifies_plural_replacement_sources_as_additions(self):
        release = {
            "published_date": "2017-06-09",
            "source_url": "https://press.spglobal.com/example",
            "source_sha256": "a" * 64,
            "text": (
                "S&P MidCap 400 constituents Align Technology Inc. (NASD: ALGN) "
                "and ANSYS Inc. (NASD: ANSS) will replace Teradata Corp. "
                "(NYSE: TDC) and Ryder System Inc. (NYSE: R) respectively in "
                "the S&P 500 effective prior to the open on Monday, June 19."
            ),
        }
        for ticker in ("ALGN", "ANSS"):
            result = verify_candidate(
                {"effective_date": "2017-06-19", "action": "ADD", "ticker": ticker},
                release,
            )
            self.assertEqual(
                "SEMANTICS_AND_DATE_VERIFIED", result["verification_status"]
            )

    def test_company_abbreviation_does_not_end_plural_replacement_clause(self):
        release = {
            "published_date": "2017-03-10",
            "source_url": "https://press.spglobal.com/example",
            "source_sha256": "a" * 64,
            "text": (
                "The changes are effective prior to the open on Monday, March 20. "
                "Advanced Micro Devices Inc. (NASD: AMD), Raymond James "
                "Financial Inc. (NYSE: RJF) and Alexandria Real Estate Equities "
                "Inc. (NYSE: ARE) will replace Urban Outfitters Inc. "
                "(NASD: URBN), Frontier Communications Corp. (NASD: FTR) and "
                "First Solar Inc. (NASD: FSLR) respectively in the S&P 500."
            ),
        }

        for ticker in ("AMD", "RJF", "ARE"):
            result = verify_candidate(
                {"effective_date": "2017-03-20", "action": "ADD", "ticker": ticker},
                release,
            )
            self.assertEqual(
                "SEMANTICS_AND_DATE_VERIFIED", result["verification_status"]
            )

    def test_does_not_attach_previous_sentence_replacement_to_addition(self):
        release = {
            "published_date": "2017-02-23",
            "source_url": "https://press.spglobal.com/example",
            "source_sha256": "a" * 64,
            "text": (
                "Old Company will replace Another Company. S&P MidCap 400 "
                "constituent Regency Centers Corp. (NYSE: REG) will replace "
                "Endo International (NASD: ENDP) in the S&P 500 effective "
                "prior to the open on Thursday, March 2."
            ),
        }

        result = verify_candidate(
            {"effective_date": "2017-03-02", "action": "ADD", "ticker": "REG"},
            release,
        )

        self.assertEqual(
            "SEMANTICS_AND_DATE_VERIFIED", result["verification_status"]
        )

    def test_classifies_plural_replacement_targets_as_removals(self):
        release = {
            "published_date": "2017-07-19",
            "source_url": "https://press.spglobal.com/example",
            "source_sha256": "b" * 64,
            "text": (
                "ResMed Inc. (NYSE: RMD), Packaging Corp. (NYSE: PKG), "
                "A.O. Smith Corp. (NYSE: AOS) and Duke Realty Corp. (NYSE: DRE) "
                "will replace Mallinckrodt plc (NYSE: MNK), Murphy Oil Corp. "
                "(NYSE: MUR), Bed Bath & Beyond Inc. (NASD: BBBY) and "
                "Transocean Ltd. (NYSE: RIG) respectively, in the S&P 500 "
                "effective prior to the open on Wednesday, July 26."
            ),
        }
        for ticker in ("MUR", "BBBY"):
            result = verify_candidate(
                {"effective_date": "2017-07-26", "action": "REMOVE", "ticker": ticker},
                release,
            )
            self.assertEqual(
                "SEMANTICS_AND_DATE_VERIFIED", result["verification_status"]
            )
        for ticker in ("RMD", "PKG"):
            result = verify_candidate(
                {"effective_date": "2017-07-26", "action": "ADD", "ticker": ticker},
                release,
            )
            self.assertEqual(
                "SEMANTICS_AND_DATE_VERIFIED", result["verification_status"]
            )

    def test_company_initials_do_not_hide_replacement_removal(self):
        release = {
            "published_date": "2017-08-24",
            "source_url": "https://press.spglobal.com/example",
            "source_sha256": "c" * 64,
            "text": (
                "SBA Communications Corp. (NASD: SBAC) will replace "
                "E. I. du Pont de Nemours and Co. (NYSE: DD) in the S&P 500 "
                "effective prior to the open on Friday, September 1."
            ),
        }
        result = verify_candidate(
            {"effective_date": "2017-09-01", "action": "REMOVE", "ticker": "DD"},
            release,
        )
        self.assertEqual(
            "SEMANTICS_AND_DATE_VERIFIED", result["verification_status"]
        )

    def test_cross_index_clause_does_not_turn_removed_ticker_into_addition(self):
        release = {
            "published_date": "2017-08-24",
            "source_url": "https://press.spglobal.com/example",
            "source_sha256": "e" * 64,
            "text": (
                "Charter Communications Inc. (NASD: CHTR) will replace "
                "E. I. du Pont de Nemours and Co. (NYSE: DD) in the S&P 100, "
                "and SBA Communications Corp. (NASD: SBAC) will replace "
                "E. I. du Pont de Nemours in the S&P 500 effective prior to "
                "the open on Friday, September 1."
            ),
        }
        result = verify_candidate(
            {"effective_date": "2017-09-01", "action": "REMOVE", "ticker": "DD"},
            release,
        )
        self.assertEqual(
            "SEMANTICS_AND_DATE_VERIFIED", result["verification_status"]
        )

    def test_no_longer_eligible_is_removal(self):
        release = {
            "published_date": "2018-06-25",
            "source_url": "https://press.spglobal.com/example",
            "source_sha256": "d" * 64,
            "text": (
                "Keurig Dr Pepper Inc. and its ticker symbol (NYSE: KDP) "
                "will no longer be eligible for inclusion in the S&P 500 "
                "prior to the open on Monday, July 2."
            ),
        }
        result = verify_candidate(
            {"effective_date": "2018-07-02", "action": "REMOVE", "ticker": "KDP"},
            release,
        )
        self.assertEqual(
            "SEMANTICS_AND_DATE_VERIFIED", result["verification_status"]
        )


if __name__ == "__main__":
    unittest.main()
