import unittest

from herd.spglobal_candidate_semantics import extract_candidate_semantics


class SpglobalCandidateSemanticsTest(unittest.TestCase):
    def _release(self, text):
        return {
            "published_date": "2017-07-19",
            "source_url": "https://press.spglobal.com/example",
            "source_sha256": "a" * 64,
            "text": text,
        }

    def test_extracts_official_date_even_when_candidate_date_is_wrong(self):
        row = extract_candidate_semantics(
            {"effective_date": "2017-07-25", "action": "REMOVE", "ticker": "RAI"},
            self._release(
                "MGM (NYSE: MGM) will replace Reynolds American (NYSE: RAI) "
                "in the S&P 500 effective prior to the open on Wednesday, July 26."
            ),
        )
        self.assertEqual(
            "OFFICIAL_SEMANTICS_CONFLICTS_WITH_CANDIDATE",
            row["extraction_status"],
        )
        self.assertEqual("2017-07-26", row["membership_session_date"])
        self.assertEqual("REMOVE", row["official_action"])

    def test_extracts_after_close_with_real_xnys_holiday_calendar(self):
        row = extract_candidate_semantics(
            {"effective_date": "2016-09-06", "action": "ADD", "ticker": "MTD"},
            {
                "published_date": "2016-08-25",
                "source_url": "https://press.spglobal.com/example",
                "source_sha256": "a" * 64,
                "text": (
                    "Mettler-Toledo (NYSE: MTD) will replace JCI (NYSE: JCI) "
                    "in the S&P 500 after the close on Friday, September 2."
                ),
            },
        )
        self.assertEqual(
            "OFFICIAL_SEMANTICS_MATCH_CANDIDATE", row["extraction_status"]
        )
        self.assertEqual("2016-09-06", row["membership_session_date"])


if __name__ == "__main__":
    unittest.main()
