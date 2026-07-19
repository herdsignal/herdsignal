import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from herd.sec_delisting_evidence import find_form25_candidates


class SecDelistingEvidenceTest(unittest.TestCase):
    def test_links_only_unique_cik_removal_inside_window(self):
        with TemporaryDirectory() as directory:
            raw = Path(directory) / "raw"
            raw.mkdir()
            (raw / "2024-Q1-master.idx").write_text(
                "CIK|Company Name|Form Type|Date Filed|Filename\n"
                "------------------------------------------------\n"
                "1|Example Inc|25-NSE|2024-01-12|edgar/data/1/form25.txt\n",
                encoding="latin-1",
            )
            events = [{
                "effective_date": "2024-01-10", "action": "REMOVE",
                "ticker": "EX", "company_name": "Example",
                "cik": "0000000001",
                "cik_link_status": "UNIQUE_CIK_NAME_CANDIDATE",
            }]
            rows, audit = find_form25_candidates(events, Path(directory))
            self.assertEqual("UNIQUE_FORM25_CANDIDATE", rows[0]["status"])
            self.assertTrue(rows[0]["filing_url"].endswith("form25.txt"))
            self.assertEqual(1, audit["eligible_removal_events"])

    def test_does_not_treat_missing_form_as_confirmed_delisting(self):
        with TemporaryDirectory() as directory:
            raw = Path(directory) / "raw"
            raw.mkdir()
            (raw / "2024-Q1-master.idx").write_text(
                "CIK|Company Name|Form Type|Date Filed|Filename\n"
                "1|Example Inc|8-K|2024-01-12|edgar/data/1/8k.txt\n",
                encoding="latin-1",
            )
            events = [{
                "effective_date": "2024-01-10", "action": "REMOVE",
                "ticker": "EX", "company_name": "Example",
                "cik": "0000000001",
                "cik_link_status": "UNIQUE_CIK_NAME_CANDIDATE",
            }]
            rows, audit = find_form25_candidates(events, Path(directory))
            self.assertEqual("NO_FORM25_IN_WINDOW", rows[0]["status"])
            self.assertFalse(audit["complete"])


if __name__ == "__main__":
    unittest.main()
