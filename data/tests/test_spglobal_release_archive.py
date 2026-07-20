import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.spglobal_release_archive import (
    ReleaseArchiveError,
    collect_direct_release_corpus,
    discover_release_links,
)


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

    def test_discovers_join_the_sp500_and_addition_titles(self):
        source = b"""
        <a href="https://press.spglobal.com/2016-08-25-Mettler-Toledo-Set-to-Join-the-S-P-500">
          Mettler-Toledo Set to Join the S&amp;P 500
        </a>
        <a href="https://press.spglobal.com/2020-11-30-Tesla-Addition-to-S-P-500">
          Implementation of Tesla's Addition to S&amp;P 500
        </a>
        """
        rows = discover_release_links(source, date(2016, 1, 1), date(2021, 1, 1))
        self.assertEqual(2, len(rows))

    def test_discovers_broad_us_indices_change_title(self):
        source = b"""
        <a href="https://press.spglobal.com/2017-03-10-S-P-Dow-Jones-Indices-Announces-Changes-to-U-S-Indices">
          S&amp;P Dow Jones Indices Announces Changes to U.S. Indices
        </a>
        """
        rows = discover_release_links(source, date(2017, 1, 1), date(2017, 12, 31))
        self.assertEqual(1, len(rows))

    def test_archives_explicit_official_release_with_hash(self):
        response = Mock()
        response.content = b"<html>official</html>"
        response.headers = {"Content-Type": "text/html"}
        response.raise_for_status = Mock()
        session = Mock()
        session.headers = {}
        session.get.return_value = response
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claims = root / "claims.csv"
            claims.write_text(
                "published_date,title,source_url\n"
                "2016-10-24,HCP,"
                "https://press.spglobal.com/2016-10-24-HCP\n",
                encoding="utf-8",
            )
            manifest = collect_direct_release_corpus(
                claims,
                root / "corpus",
                user_agent="Research contact test@example.com",
                session=session,
            )
            self.assertEqual(1, manifest["release_documents"])
            self.assertEqual(1, len(list((root / "corpus/evidence").iterdir())))

    def test_rejects_nonofficial_direct_release(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claims = root / "claims.csv"
            claims.write_text(
                "published_date,title,source_url\n"
                "2016-10-24,HCP,https://example.com/2016-10-24-HCP\n",
                encoding="utf-8",
            )
            session = Mock()
            session.headers = {}
            with self.assertRaises(ReleaseArchiveError):
                collect_direct_release_corpus(
                    claims,
                    root / "corpus",
                    user_agent="Research contact test@example.com",
                    session=session,
                )

    def test_archives_official_spdji_pdf_document(self):
        response = Mock()
        response.content = b"%PDF-1.4 official"
        response.headers = {"Content-Type": "application/pdf"}
        response.raise_for_status = Mock()
        session = Mock()
        session.headers = {}
        session.get.return_value = response
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claims = root / "claims.csv"
            claims.write_text(
                "published_date,title,source_url\n"
                "2018-01-24,PX,"
                "https://www.spglobal.com/spdji/en/documents/"
                "indexnews/announcements/px.pdf\n",
                encoding="utf-8",
            )
            collect_direct_release_corpus(
                claims,
                root / "corpus",
                user_agent="Research contact test@example.com",
                session=session,
            )
            evidence = list((root / "corpus/evidence").iterdir())
            self.assertEqual(".pdf", evidence[0].suffix)


if __name__ == "__main__":
    unittest.main()
