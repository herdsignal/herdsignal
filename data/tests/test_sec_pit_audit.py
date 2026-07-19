import unittest
from datetime import date

from herd.sec_point_in_time_fundamentals import normalize_companyfacts

from tests.test_sec_point_in_time_fundamentals import companyfacts_payload


class SecPitAuditTest(unittest.TestCase):
    def test_filters_facts_to_requested_filing_period(self):
        rows, audit = normalize_companyfacts(
            companyfacts_payload(),
            {"old": "2024-02-01T21:00:00+00:00"},
            filed_from=date(2024, 1, 1),
            filed_to=date(2024, 2, 15),
        )
        self.assertEqual(["old"], [row["accession_number"] for row in rows])
        self.assertEqual(0, audit["missing_acceptances"])
        self.assertTrue(audit["point_in_time_ready"])


if __name__ == "__main__":
    unittest.main()
