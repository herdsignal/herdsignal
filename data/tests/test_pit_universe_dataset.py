import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.pit_universe_dataset import (
    PitUniverseError,
    community_intervals,
    create_community_dataset,
    verify_dataset,
)


class PitUniverseDatasetTest(unittest.TestCase):
    def _source(self, root: Path) -> Path:
        path = root / "source.csv"
        first = ",".join(f"T{i:03d}" for i in range(500))
        second = ",".join([*(f"T{i:03d}" for i in range(1, 500)), "NEW"])
        path.write_text(
            f'date,tickers\n2020-01-01,"{first}"\n2020-01-02,"{second}"\n',
            encoding="utf-8",
        )
        return path

    def test_community_source_is_never_marked_survivorship_safe(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = create_community_dataset(
                "community-001",
                self._source(root),
                source_uri="https://example.test/source",
                root=root / "output",
            )
            manifest = verify_dataset(dataset)
            self.assertFalse(manifest["quality"]["survivorship_safe"])
            self.assertFalse(manifest["quality"]["stable_security_ids"])

    def test_membership_uses_end_exclusive_intervals(self):
        with TemporaryDirectory() as directory:
            source = self._source(Path(directory))
            memberships, events, _ = community_intervals(
                source, source_uri="https://example.test/source"
            )
            removed = next(item for item in memberships if item.ticker == "T000")
            self.assertEqual(removed.effective_from, "2020-01-01")
            self.assertEqual(removed.effective_to, "2020-01-02")
            self.assertIn(
                {"effective_date": "2020-01-02", "event": "REMOVE", "ticker": "T000"},
                events,
            )

    def test_implausible_constituent_count_is_rejected(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "bad.csv"
            source.write_text('date,tickers\n2020-01-01,"A,B"\n2020-01-02,"A,B"\n')
            with self.assertRaises(PitUniverseError):
                community_intervals(source, source_uri="test")


if __name__ == "__main__":
    unittest.main()
