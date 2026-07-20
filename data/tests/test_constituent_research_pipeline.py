import tempfile
import unittest
from datetime import date
from pathlib import Path

from herd.constituent_research_pipeline import (
    ConstituentResearchPipelineError,
    hash_path,
    normalize_candidates,
    regression_failures,
    write_csv,
)


class ConstituentResearchPipelineTest(unittest.TestCase):
    def test_normalizes_and_filters_immutable_community_events(self):
        rows = normalize_candidates(
            [
                {"effective_date": "2016-07-17", "event": "ADD", "ticker": "OLD"},
                {"effective_date": "2016-07-18", "event": "ADD", "ticker": "abc"},
                {"effective_date": "2026-07-18", "event": "REMOVE", "ticker": "LATE"},
            ],
            start=date(2016, 7, 18),
            end=date(2026, 7, 17),
        )
        self.assertEqual(
            [{"effective_date": "2016-07-18", "action": "ADD", "ticker": "ABC"}],
            rows,
        )

    def test_rejects_resolved_candidate_regression(self):
        failures = regression_failures(
            reconciliation=[{
                "candidate_effective_date": "2020-01-02",
                "action": "ADD",
                "ticker": "AAA",
                "status": "NO_OFFICIAL_DOCUMENT_MATCH",
            }],
            ledger_audit={"verified_official_events": 1},
            replay_audit={"verified_events": 1, "blocked_events": 1, "errors": 0},
            previous_reconciliation=[{
                "candidate_effective_date": "2020-01-02",
                "action": "ADD",
                "ticker": "AAA",
                "status": "OFFICIAL_PROSE_EXACT",
            }],
        )
        self.assertTrue(any("regressed" in failure for failure in failures))

    def test_rejects_metric_regression_and_replay_errors(self):
        failures = regression_failures(
            reconciliation=[],
            ledger_audit={"verified_official_events": 9},
            replay_audit={"verified_events": 9, "blocked_events": 3, "errors": 1},
            previous_replay_audit={"verified_events": 10, "blocked_events": 2},
        )
        self.assertEqual(3, len(failures))

    def test_hashes_directory_content_and_relative_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.txt").write_text("a", encoding="utf-8")
            first = hash_path(root)
            (root / "a.txt").write_text("b", encoding="utf-8")
            self.assertNotEqual(first, hash_path(root))

    def test_rejects_duplicate_normalized_candidates(self):
        with self.assertRaises(ConstituentResearchPipelineError):
            normalize_candidates(
                [
                    {"effective_date": "2020-01-02", "event": "ADD", "ticker": "AAA"},
                    {"effective_date": "2020-01-02", "action": "ADD", "ticker": "AAA"},
                ],
                start=date(2020, 1, 1),
                end=date(2020, 12, 31),
            )

    def test_writes_header_for_completed_empty_backlog(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "backlog.csv"
            write_csv(output, [], empty_fields=("ticker", "status"))
            self.assertEqual("ticker,status\n", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
