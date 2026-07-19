import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.data_snapshot import create_snapshot
from herd.walk_forward_artifacts import (
    WalkForwardConfig,
    WalkForwardError,
    build_anchored_folds,
    create_walk_forward_run,
    verify_walk_forward_run,
)


class WalkForwardArtifactsTest(unittest.TestCase):
    def test_folds_are_chronological_with_exact_gap(self):
        calendar = pd.bdate_range("2018-01-02", "2025-12-31")
        config = WalkForwardConfig(
            min_train_years=4,
            test_years=1,
            step_years=1,
            purge_days=5,
            embargo_days=10,
        )

        folds = build_anchored_folds(calendar, config)

        self.assertGreaterEqual(len(folds), 3)
        for fold in folds:
            self.assertEqual(fold.gap_observations, 15)
            self.assertLess(pd.Timestamp(fold.train_end), pd.Timestamp(fold.test_start))
        for previous, current in zip(folds, folds[1:]):
            self.assertLess(pd.Timestamp(previous.test_end), pd.Timestamp(current.test_start))

    def test_short_calendar_is_rejected(self):
        with self.assertRaises(WalkForwardError):
            build_anchored_folds(pd.bdate_range("2024-01-01", "2025-01-01"))

    def test_run_persists_verified_daily_paths(self):
        dates = pd.bdate_range("2017-01-02", "2025-12-31")

        def collector(ticker: str, *, period: str) -> pd.DataFrame:
            offset = {"SPY": 0.0, "QQQ": 10.0}[ticker]
            trend = np.linspace(100 + offset, 240 + offset, len(dates))
            cycle = np.sin(np.arange(len(dates)) / 30) * 2
            close = trend + cycle
            return pd.DataFrame(
                {
                    "Date": dates,
                    "Open": close * 0.999,
                    "High": close * 1.01,
                    "Low": close * 0.99,
                    "Close": close,
                    "Volume": 1_000_000 + np.arange(len(dates)),
                }
            )

        with TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = create_snapshot(
                "snapshot-001",
                tickers=["SPY", "QQQ"],
                period="10y",
                root=root / "snapshots",
                collector=collector,
                created_at=datetime(2026, 7, 19, tzinfo=timezone.utc),
            )
            run = create_walk_forward_run(
                "run-001",
                snapshot,
                root=root / "runs",
                created_at=datetime(2026, 7, 19, tzinfo=timezone.utc),
            )

            manifest = verify_walk_forward_run(run)
            daily = pd.read_csv(run / "daily_returns.csv.gz")
            folds = pd.read_csv(run / "folds.csv")

            self.assertEqual(manifest["snapshot"]["snapshot_id"], "snapshot-001")
            self.assertEqual(
                manifest["blind_holdout_status"],
                "NOT_ASSIGNED_BY_THIS_RUN",
            )
            self.assertEqual(set(daily["candidate"]), {"B0", "B1", "B2", "B3"})
            self.assertGreater(len(folds), 0)
            self.assertGreater(len(daily), 0)


if __name__ == "__main__":
    unittest.main()
