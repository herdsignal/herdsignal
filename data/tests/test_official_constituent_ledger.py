import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.official_constituent_ledger import (
    OfficialLedgerError,
    audit_candidate_coverage,
    load_official_ledger,
    replay_membership,
    verify_evidence,
)


class OfficialConstituentLedgerTest(unittest.TestCase):
    def _ledger(self, root: Path, *, host: str = "press.spglobal.com") -> Path:
        evidence = root / "source.html"
        evidence.write_text("official release", encoding="utf-8")
        import hashlib
        digest = hashlib.sha256(evidence.read_bytes()).hexdigest()
        stored = root / f"{digest}.html"
        evidence.rename(stored)
        ledger = root / "ledger.csv"
        ledger.write_text(
            "announcement_date,effective_date,action,ticker,company_name,source_url,source_sha256\n"
            f"2024-01-01,2024-01-05,REMOVE,OLD,Old Inc,https://{host}/release,{digest}\n"
            f"2024-01-01,2024-01-05,ADD,NEW,New Inc,https://{host}/release,{digest}\n",
            encoding="utf-8",
        )
        return ledger

    def test_replays_paired_official_change(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            events = load_official_ledger(self._ledger(root))
            verify_evidence(events, root)
            baseline = {f"T{i:03d}" for i in range(499)} | {"OLD"}
            snapshots, summary = replay_membership(baseline, events)
            self.assertEqual(snapshots[0]["added"], ["NEW"])
            self.assertEqual(snapshots[0]["removed"], ["OLD"])
            self.assertEqual(summary["final_count"], 500)

    def test_rejects_non_official_evidence_host(self):
        with TemporaryDirectory() as directory:
            with self.assertRaises(OfficialLedgerError):
                load_official_ledger(self._ledger(Path(directory), host="example.com"))

    def test_missing_evidence_file_fails_closed(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            events = load_official_ledger(self._ledger(root))
            next(root.glob("*.html")).unlink()
            with self.assertRaises(OfficialLedgerError):
                verify_evidence(events, root)

    def test_candidate_coverage_exposes_unverified_events(self):
        with TemporaryDirectory() as directory:
            events = load_official_ledger(self._ledger(Path(directory)))
            audit = audit_candidate_coverage(
                events,
                [
                    {"effective_date": "2024-01-05", "event": "ADD", "ticker": "NEW"},
                    {"effective_date": "2024-01-05", "event": "REMOVE", "ticker": "MISSING"},
                ],
            )
            self.assertFalse(audit["complete"])
            self.assertEqual(audit["coverage"], 0.5)


if __name__ == "__main__":
    unittest.main()
