import unittest

from herd.spglobal_pdf_archive import (
    SpglobalPdfArchiveError,
    as_pdf_url,
    corroborates_release,
)


class SpglobalPdfArchiveTest(unittest.TestCase):
    def test_adds_pdf_query_without_losing_existing_query(self):
        self.assertEqual(
            "https://press.spglobal.com/release?kw=test&asPDF=1",
            as_pdf_url("https://press.spglobal.com/release?kw=test"),
        )

    def test_rejects_non_official_host(self):
        with self.assertRaises(SpglobalPdfArchiveError):
            as_pdf_url("https://example.com/release")

    def test_requires_sp500_and_title_token_coverage(self):
        release = {
            "title": "Live Nation Entertainment Zebra Technologies Set to Join S&P 500"
        }
        self.assertTrue(corroborates_release(
            "Live Nation Entertainment and Zebra Technologies will join the S&P 500.",
            release,
        ))
        self.assertFalse(corroborates_release(
            "Live Nation Entertainment published quarterly earnings.",
            release,
        ))


if __name__ == "__main__":
    unittest.main()
