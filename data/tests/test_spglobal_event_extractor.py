import unittest

from herd.spglobal_event_extractor import (
    OfficialEventExtractionError,
    extract_table_events,
    parse_effective_date,
)


class SpglobalEventExtractorTest(unittest.TestCase):
    def test_extracts_only_sp500_rows_from_official_table(self):
        content = b"""
        <table>
          <tr><th>Effective Date</th><th>Index Name</th><th>Action</th>
              <th>Company Name</th><th>Ticker</th><th>GICS Sector</th></tr>
          <tr><td>Sept. 21, 2020</td><td>S&amp;P 500</td><td>Addition</td>
              <td>Etsy</td><td>ETSY</td><td>Consumer</td></tr>
          <tr><td></td><td>S&amp;P 400</td><td>Deletion</td>
              <td>Other</td><td>OTHER</td><td>Industrials</td></tr>
        </table>
        """
        events, unresolved = extract_table_events(
            content,
            announcement_date="2020-09-04",
            source_url="https://press.spglobal.com/example",
            source_sha256="a" * 64,
        )
        self.assertEqual(1, len(events))
        self.assertEqual([], unresolved)
        self.assertEqual("2020-09-21", events[0]["effective_date"])
        self.assertEqual("ADD", events[0]["action"])
        self.assertEqual("STRUCTURE_VERIFIED", events[0]["review_status"])

    def test_parses_long_and_abbreviated_months(self):
        self.assertEqual("2020-10-07", parse_effective_date("October 7, 2020"))
        self.assertEqual("2020-09-21", parse_effective_date("Sept. 21, 2020"))

    def test_rejects_unknown_action_in_matching_table(self):
        content = b"""
        <table>
          <tr><th>Effective Date</th><th>Index Name</th><th>Action</th>
              <th>Company Name</th><th>Ticker</th></tr>
          <tr><td>June 1, 2024</td><td>S&amp;P 500</td><td>Maybe</td>
              <td>Example</td><td>EX</td></tr>
        </table>
        """
        with self.assertRaises(OfficialEventExtractionError):
            extract_table_events(
                content, announcement_date="2024-05-01",
                source_url="https://press.spglobal.com/example",
                source_sha256="a" * 64,
            )


if __name__ == "__main__":
    unittest.main()
