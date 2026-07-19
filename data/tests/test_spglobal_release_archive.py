import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.spglobal_release_archive import discover_release_links


class SpglobalReleaseArchiveTest(unittest.TestCase):
    def test_discovers_only_dated_sp500_change_releases(self):
        source = b"""
        <a href="https://press.spglobal.com/2024-03-01-A-Set-to-Join-S-P-500">
          A Set to Join S&amp;P 500
        </a>
        <a href="https://press.spglobal.com/2024-03-02-S-P-500-Research">
          S&amp;P 500 Research Report
        </a>
        <a href="https://example.com/2024-03-01-X">X Set to Join S&amp;P 500</a>
        """
        rows = discover_release_links(source, date(2024, 1, 1), date(2024, 12, 31))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "REQUIRES_EVENT_EXTRACTION")


if __name__ == "__main__":
    unittest.main()
