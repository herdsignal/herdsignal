import unittest
from datetime import date

from herd.sec_pit_corpus import overlapping_submission_files, unique_ciks


class SecPitCorpusTest(unittest.TestCase):
    def test_keeps_only_unique_cik_candidates(self):
        rows = [
            {"cik": "1", "cik_link_status": "UNIQUE_CIK_NAME_CANDIDATE"},
            {"cik": "2", "cik_link_status": "AMBIGUOUS_CIK_NAME_CANDIDATE"},
            {"cik": "1", "cik_link_status": "UNIQUE_CIK_NAME_CANDIDATE"},
        ]
        self.assertEqual(["0000000001"], unique_ciks(rows))

    def test_selects_only_history_files_overlapping_period(self):
        payload = {"filings": {"files": [
            {"name": "old.json", "filingFrom": "2010-01-01", "filingTo": "2015-12-31"},
            {"name": "use.json", "filingFrom": "2016-01-01", "filingTo": "2018-01-01"},
        ]}}
        self.assertEqual(
            ["use.json"],
            overlapping_submission_files(
                payload, date(2016, 7, 18), date(2026, 7, 17)
            ),
        )


if __name__ == "__main__":
    unittest.main()
