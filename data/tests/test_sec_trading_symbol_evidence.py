import unittest
from datetime import date

from herd.sec_trading_symbol_evidence import (
    classify_pair,
    extract_symbol_change_dates,
    extract_trading_symbols,
    filing_rows,
    select_surrounding_filings,
)


class SecTradingSymbolEvidenceTest(unittest.TestCase):
    def test_extracts_inline_xbrl_trading_symbol(self):
        content = (
            b'<ix:nonNumeric name="dei:TradingSymbol">META</ix:nonNumeric>'
        )
        self.assertEqual(["META"], extract_trading_symbols(content))

    def test_extracts_explicit_symbol_change_date(self):
        content = (
            b"<p>will begin trading under the new ticker symbol META "
            b"prior to market open on June 9, 2022.</p>"
        )
        self.assertEqual(
            ["2022-06-09"], extract_symbol_change_dates(content, "META")
        )

    def test_extracts_reverse_change_phrase_and_commenced_trading(self):
        reverse = (
            b"<p>We are changing our ticker to BALL effective May 10, 2022.</p>"
        )
        commenced = (
            b"<p>On April 11, 2022, WBD common stock commenced trading on "
            b"Nasdaq under the ticker symbol WBD.</p>"
        )

        self.assertEqual(
            ["2022-05-10"], extract_symbol_change_dates(reverse, "BALL")
        )
        self.assertEqual(
            ["2022-04-11"], extract_symbol_change_dates(commenced, "WBD")
        )

    def test_extracts_began_trading_under_symbol_wording(self):
        content = (
            b"<p>Truist began trading on the New York Stock Exchange under "
            b"the symbol TFC on December 9, 2019.</p>"
        )

        self.assertEqual(
            ["2019-12-09"], extract_symbol_change_dates(content, "TFC")
        )

    def test_prefers_date_nearest_ticker_change_over_name_change_date(self):
        content = (
            b"<p>Effective August 8, 2019, the company changed its name. "
            b"The NYSE ticker was changed to GL on August 9, 2019.</p>"
        )
        self.assertEqual(
            ["2019-08-09"], extract_symbol_change_dates(content, "GL")
        )

    def test_selects_filings_on_both_sides(self):
        rows = [
            {
                "accession_number": str(i),
                "filing_date": value,
                "form": "10-Q",
                "primary_document": "x.htm",
            }
            for i, value in enumerate(
                ["2022-01-01", "2022-05-01", "2022-06-10", "2022-08-01"]
            )
        ]
        selected = select_surrounding_filings(rows, date(2022, 6, 9))
        self.assertEqual(4, len(selected))

    def test_selects_enough_filings_to_reach_quarterly_confirmation(self):
        rows = [
            {
                "accession_number": str(i),
                "filing_date": f"2022-06-{i:02d}",
                "form": "8-K" if i < 9 else "10-Q",
                "primary_document": "x.htm",
            }
            for i in range(1, 10)
        ]

        selected = select_surrounding_filings(rows, date(2022, 6, 1))

        self.assertEqual(9, len(selected))
        self.assertIn("9", {row["accession_number"] for row in selected})

    def test_preserves_periodic_report_when_many_current_reports_follow(self):
        rows = [{
            "accession_number": "quarterly",
            "filing_date": "2022-08-10",
            "form": "10-Q",
            "primary_document": "quarterly.htm",
        }] + [
            {
                "accession_number": f"current-{day}",
                "filing_date": f"2022-07-{day:02d}",
                "form": "8-K",
                "primary_document": "current.htm",
            }
            for day in range(2, 12)
        ]

        selected = select_surrounding_filings(rows, date(2022, 7, 1))

        self.assertIn("quarterly", {row["accession_number"] for row in selected})

    def test_reads_supplemental_submission_shape(self):
        rows = filing_rows({
            "accessionNumber": ["0001"],
            "filingDate": ["2020-01-01"],
            "form": ["10-K"],
            "primaryDocument": ["report.htm"],
        })
        self.assertEqual("0001", rows[0]["accession_number"])

    def test_requires_old_before_and_new_after_under_same_cik(self):
        result = classify_pair(
            {
                "new_candidate_date": "2022-06-09",
                "old_ticker": "FB",
                "new_ticker": "META",
            },
            [
                {
                    "filing_date": "2022-05-01",
                    "trading_symbols": ["FB"],
                    "accession_number": "a",
                },
                {
                    "filing_date": "2022-06-10",
                    "trading_symbols": ["META"],
                    "symbol_change_dates": ["2022-06-09"],
                    "accession_number": "b",
                },
            ],
        )
        self.assertEqual(
            "SEC_IDENTITY_AND_EFFECTIVE_DATE_VERIFIED", result["identity_status"]
        )
        self.assertEqual("2022-06-09", result["resolved_effective_date"])

    def test_prefers_candidate_date_when_official_context_contains_other_dates(self):
        result = classify_pair(
            {
                "new_candidate_date": "2022-11-08",
                "old_ticker": "NLOK",
                "new_ticker": "GEN",
            },
            [
                {
                    "filing_date": "2022-11-01",
                    "trading_symbols": ["NLOK"],
                    "symbol_change_dates": [],
                    "accession_number": "a",
                },
                {
                    "filing_date": "2022-11-09",
                    "trading_symbols": ["GEN"],
                    "symbol_change_dates": [
                        "2022-11-02", "2022-11-07", "2022-11-08"
                    ],
                    "accession_number": "b",
                },
            ],
        )
        self.assertEqual("2022-11-08", result["resolved_effective_date"])


if __name__ == "__main__":
    unittest.main()
