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
