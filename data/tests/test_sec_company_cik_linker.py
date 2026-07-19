import unittest

from herd.sec_company_cik_linker import canonical_name, link_events


class SecCompanyCikLinkerTest(unittest.TestCase):
    def test_normalizes_company_suffix_without_dropping_core_name(self):
        self.assertEqual(
            "APPLE", canonical_name("Apple Inc.", remove_suffixes=True)
        )
        self.assertEqual(
            "H AND R BLOCK", canonical_name("H&R Block, Inc.", remove_suffixes=True)
        )

    def test_links_only_unique_name_candidate(self):
        event = {"company_name": "Apple Inc.", "ticker": "AAPL"}
        detail = {
            "sec_names": {"APPLE INC"}, "forms": {"10-K"},
            "first_filed": "2016-01-01", "last_filed": "2026-01-01",
        }
        matches = {("EXACT", "APPLE INC"): {"0000320193": detail}}
        rows, audit = link_events([event], matches)
        self.assertEqual("0000320193", rows[0]["cik"])
        self.assertEqual("UNIQUE_CIK_NAME_CANDIDATE", rows[0]["cik_link_status"])
        self.assertTrue(audit["complete"])

    def test_ambiguous_name_does_not_choose_cik(self):
        event = {"company_name": "Example", "ticker": "EX"}
        detail = {
            "sec_names": {"EXAMPLE INC"}, "forms": {"10-K"},
            "first_filed": "2016-01-01", "last_filed": "2026-01-01",
        }
        matches = {
            ("BASE", "EXAMPLE"): {"0000000001": detail, "0000000002": detail}
        }
        rows, audit = link_events([event], matches)
        self.assertEqual("", rows[0]["cik"])
        self.assertEqual("AMBIGUOUS_CIK_NAME_CANDIDATE", rows[0]["cik_link_status"])
        self.assertFalse(audit["complete"])


if __name__ == "__main__":
    unittest.main()
