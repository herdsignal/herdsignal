import unittest

from herd.spglobal_evidence_matcher import match_backlog


class SpglobalEvidenceMatcherTest(unittest.TestCase):
    def test_matches_exchange_ticker_inside_bounded_window(self):
        backlog = [{"effective_date": "2024-03-18", "action": "ADD", "ticker": "SMCI"}]
        releases = [{
            "published_date": "2024-03-01",
            "source_url": "https://press.spglobal.com/example",
            "source_sha256": "a" * 64,
            "text": "Super Micro Computer (NASD: SMCI) will replace another company.",
        }]
        matches = match_backlog(backlog, releases)
        self.assertEqual("SMCI", matches[0]["ticker"])
        self.assertEqual("REQUIRES_HUMAN_REVIEW", matches[0]["review_status"])

    def test_does_not_match_short_ticker_as_plain_text(self):
        backlog = [{"effective_date": "2024-03-18", "action": "REMOVE", "ticker": "A"}]
        releases = [{
            "published_date": "2024-03-01",
            "source_url": "https://press.spglobal.com/example",
            "source_sha256": "a" * 64,
            "text": "This is a routine S&P 500 announcement.",
        }]
        self.assertEqual([], match_backlog(backlog, releases))

    def test_rejects_release_outside_window(self):
        backlog = [{"effective_date": "2024-03-18", "action": "ADD", "ticker": "SMCI"}]
        releases = [{
            "published_date": "2023-01-01",
            "source_url": "https://press.spglobal.com/example",
            "source_sha256": "a" * 64,
            "text": "Super Micro Computer (NASD: SMCI) will replace another company.",
        }]
        self.assertEqual([], match_backlog(backlog, releases))


if __name__ == "__main__":
    unittest.main()
