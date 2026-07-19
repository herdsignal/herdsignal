import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.data_snapshot import SnapshotError, create_snapshot, load_snapshot, verify_snapshot


def _prices(_ticker: str, *, period: str) -> pd.DataFrame:
    assert period == "5y"
    return pd.DataFrame(
        {
            "Date": ["2024-01-03", "2024-01-02"],
            "Open": [101.0, 100.0],
            "High": [103.0, 102.0],
            "Low": [100.0, 99.0],
            "Close": [102.0, 101.0],
            "Volume": [1_100, 1_000],
        }
    )


class DataSnapshotTest(unittest.TestCase):
    def test_snapshot_is_verified_and_loadable(self):
        with TemporaryDirectory() as directory:
            snapshot = create_snapshot(
                "test-001",
                tickers=["SPY", "QQQ"],
                period="5y",
                root=Path(directory),
                collector=_prices,
                created_at=datetime(2026, 7, 19, tzinfo=timezone.utc),
            )

            manifest = verify_snapshot(snapshot)
            frames, loaded_manifest = load_snapshot(snapshot, tickers=["SPY"])

            self.assertEqual(manifest["snapshot_sha256"], loaded_manifest["snapshot_sha256"])
            self.assertEqual(manifest["coverage"], 1.0)
            self.assertEqual(
                frames["SPY"]["Date"].dt.strftime("%Y-%m-%d").tolist(),
                ["2024-01-02", "2024-01-03"],
            )

    def test_snapshot_refuses_overwrite(self):
        with TemporaryDirectory() as directory:
            kwargs = dict(
                tickers=["SPY"],
                period="5y",
                root=Path(directory),
                collector=_prices,
                created_at=datetime(2026, 7, 19, tzinfo=timezone.utc),
            )
            create_snapshot("test-001", **kwargs)

            with self.assertRaisesRegex(SnapshotError, "already exists"):
                create_snapshot("test-001", **kwargs)

    def test_snapshot_detects_tampered_price_file(self):
        with TemporaryDirectory() as directory:
            snapshot = create_snapshot(
                "test-001",
                tickers=["SPY"],
                period="5y",
                root=Path(directory),
                collector=_prices,
            )
            price_path = snapshot / "prices" / "SPY.csv.gz"
            price_path.write_bytes(price_path.read_bytes() + b"tampered")

            with self.assertRaisesRegex(SnapshotError, "checksum mismatch"):
                verify_snapshot(snapshot)

    def test_snapshot_fails_closed_when_coverage_is_incomplete(self):
        def failing_collector(ticker: str, *, period: str) -> pd.DataFrame:
            if ticker == "QQQ":
                raise RuntimeError("provider error")
            return _prices(ticker, period=period)

        with TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(SnapshotError, "coverage"):
                create_snapshot(
                    "test-001",
                    tickers=["SPY", "QQQ"],
                    period="5y",
                    root=root,
                    collector=failing_collector,
                )
            self.assertFalse((root / "test-001").exists())


if __name__ == "__main__":
    unittest.main()
