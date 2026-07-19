import unittest

from herd.spglobal_identity_change import classify_identity_candidate


class SpglobalIdentityChangeTest(unittest.TestCase):
    def _release(self, text):
        return {
            "published_date": "2020-03-31",
            "source_url": "https://press.spglobal.com/example",
            "source_sha256": "a" * 64,
            "text": text,
        }

    def test_classifies_old_ticker_with_explicit_index_continuity(self):
        row = classify_identity_candidate(
            {"effective_date": "2020-04-03", "action": "REMOVE", "ticker": "UTX"},
            self._release(
                "S&P 500 and 100 constituent United Technologies (NYSE: UTX) "
                "will remain in the S&P 500. It will change its name and its "
                "ticker symbol to RTX."
            ),
        )
        self.assertEqual(
            "OFFICIAL_INDEX_CONTINUITY_TICKER_CHANGE", row["identity_status"]
        )
        self.assertEqual("UTX", row["old_ticker"])
        self.assertEqual("RTX", row["new_ticker"])
        self.assertEqual("NOT_EXPLICITLY_VERIFIED", row["effective_date_status"])

    def test_classifies_new_ticker_from_name_and_ticker_change(self):
        row = classify_identity_candidate(
            {"effective_date": "2020-03-03", "action": "ADD", "ticker": "TT"},
            self._release(
                'S&P 500 constituent Ingersoll-Rand (NYSE: IR) will change its '
                'name and ticker to Trane Technologies (NYSE: TT), and Trane '
                'will remain in the S&P 500.'
            ),
        )
        self.assertEqual(
            "OFFICIAL_INDEX_CONTINUITY_TICKER_CHANGE", row["identity_status"]
        )
        self.assertEqual("IR", row["old_ticker"])
        self.assertEqual("TT", row["new_ticker"])

    def test_keeps_constituent_ticker_change_date_open_without_timing(self):
        row = classify_identity_candidate(
            {"effective_date": "2019-12-05", "action": "REMOVE", "ticker": "CBS"},
            self._release(
                "S&P 500 constituent CBS Corp. (NYSE: CBS) is acquiring Viacom. "
                "Post acquisition, CBS will change its name and will trade on "
                "NASDAQ under ticker VIAC."
            ),
        )
        self.assertEqual(
            "OFFICIAL_CONSTITUENT_TICKER_CHANGE_REQUIRES_DATE",
            row["identity_status"],
        )


if __name__ == "__main__":
    unittest.main()
