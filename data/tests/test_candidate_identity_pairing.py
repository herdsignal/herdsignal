import unittest

from herd.candidate_identity_pairing import (
    canonical_ticker,
    pair_identity_candidates,
)


class CandidateIdentityPairingTest(unittest.TestCase):
    def test_normalizes_share_class_and_previous_annotation(self):
        self.assertEqual("BRKB", canonical_ticker("BRK.B"))
        self.assertEqual("BRKB", canonical_ticker("BRK-B"))
        self.assertEqual("RVTY", canonical_ticker("RVTY (PREVIOUSLY PKI)"))

    def test_pairs_nearby_unresolved_events_without_promoting_them(self):
        rows, audit = pair_identity_candidates(
            [
                {
                    "candidate_effective_date": "2022-06-09",
                    "action": "REMOVE",
                    "ticker": "FB",
                    "status": "NO_OFFICIAL_DOCUMENT_MATCH",
                },
                {
                    "candidate_effective_date": "2022-06-09",
                    "action": "ADD",
                    "ticker": "META",
                    "status": "NO_OFFICIAL_DOCUMENT_MATCH",
                },
                {
                    "candidate_effective_date": "2022-06-09",
                    "action": "ADD",
                    "ticker": "OTHER",
                    "status": "OFFICIAL_TABLE_EXACT",
                },
            ],
            [{"ticker": "META", "cik": "0001326801"}],
        )
        self.assertEqual(1, len(rows))
        self.assertEqual("REQUIRES_SEC_TRADING_SYMBOL_EVIDENCE", rows[0]["pairing_status"])
        self.assertEqual(0, audit["verified_identity_changes"])
        self.assertEqual(0, audit["membership_events_reclassified"])

    def test_pairs_format_change_without_current_cik(self):
        rows, _ = pair_identity_candidates(
            [
                {
                    "candidate_effective_date": "2023-05-09",
                    "action": "REMOVE",
                    "ticker": "BF-B",
                    "status": "NO_OFFICIAL_DOCUMENT_MATCH",
                },
                {
                    "candidate_effective_date": "2023-05-09",
                    "action": "ADD",
                    "ticker": "BF.B",
                    "status": "NO_OFFICIAL_DOCUMENT_MATCH",
                },
            ],
            [{"ticker": "BF-B", "cik": "0000014693"}],
        )
        self.assertEqual("SYMBOL_FORMAT_CONTINUITY_CANDIDATE", rows[0]["pairing_status"])
        self.assertEqual("0000014693", rows[0]["candidate_cik"])

    def test_does_not_pair_identical_ticker(self):
        rows, _ = pair_identity_candidates(
            [
                {
                    "candidate_effective_date": "2023-06-03",
                    "action": "ADD",
                    "ticker": "PANW",
                    "status": "NO_OFFICIAL_DOCUMENT_MATCH",
                },
                {
                    "candidate_effective_date": "2023-06-04",
                    "action": "REMOVE",
                    "ticker": "PANW",
                    "status": "NO_OFFICIAL_DOCUMENT_MATCH",
                },
            ],
            [{"ticker": "PANW", "cik": "0001327567"}],
        )
        self.assertEqual([], rows)


if __name__ == "__main__":
    unittest.main()
