import csv
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.pit_diagnostic_snapshot import (
    PitDiagnosticSnapshotError,
    create_snapshot,
    verify_snapshot,
)


class PitDiagnosticSnapshotTest(unittest.TestCase):
    def _pipeline(self, root: Path, *, replay_errors: int = 0) -> Path:
        source = root / "pipeline"
        source.mkdir()
        blockers = [
            {
                "candidate_effective_date": "2018-11-06",
                "action": "ADD",
                "ticker": "LIN",
                "event_status": "UNRESOLVED",
                "promotion_allowed": "false",
            },
            {
                "candidate_effective_date": "2020-11-17",
                "action": "SUCCESSION",
                "ticker": "VTRS",
                "event_status": "DIAGNOSTIC_CORPORATE_CONTINUITY",
                "promotion_allowed": "false",
            },
        ]
        with (source / "blocker_backlog.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(blockers[0]))
            writer.writeheader()
            writer.writerows(blockers)
        (source / "integrated_event_ledger.csv").write_text(
            "effective_date,action,ticker,event_status\n"
            "2020-01-02,ADD,AAA,VERIFIED_OFFICIAL_EVENT\n",
            encoding="utf-8",
        )
        replay = {
            "audit": {
                "errors": replay_errors,
                "blocked_events": 2,
                "final_count": 500,
            },
            "snapshots": [],
        }
        (source / "replay.json").write_text(
            json.dumps(replay), encoding="utf-8"
        )
        manifest = {
            "format_version": "herd-constituent-research-pipeline-v1",
            "period": {
                "start": "2016-07-18",
                "end": "2026-07-17",
            },
            "gates": {
                "regression_failures": [],
                "replay_errors": replay_errors,
                "blocked_events": 2,
                "replay_complete": False,
                "survivorship_safe": False,
            },
        }
        (source / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        return source

    def test_freezes_diagnostic_source_without_promoting_it(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = create_snapshot(
                "pit-diagnostic-v1",
                self._pipeline(root),
                root=root / "snapshots",
                created_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
            )
            manifest = verify_snapshot(snapshot)
            self.assertEqual("PIT_DIAGNOSTIC_V1", manifest["status"])
            self.assertFalse(manifest["quality"]["survivorship_safe"])
            self.assertEqual(2, manifest["quality"]["blocked_events"])
            self.assertIn(
                "FINAL_MODEL_ADOPTION",
                manifest["policy"]["forbidden_uses"],
            )

    def test_rejects_source_with_replay_errors(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(PitDiagnosticSnapshotError):
                create_snapshot(
                    "pit-diagnostic-v1",
                    self._pipeline(root, replay_errors=1),
                    root=root / "snapshots",
                )

    def test_detects_artifact_tampering(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = create_snapshot(
                "pit-diagnostic-v1",
                self._pipeline(root),
                root=root / "snapshots",
            )
            (snapshot / "replay.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(PitDiagnosticSnapshotError):
                verify_snapshot(snapshot)


if __name__ == "__main__":
    unittest.main()
