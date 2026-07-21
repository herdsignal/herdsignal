from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
import pytest

from herd.long_price_snapshot import (
    LongPriceSnapshotError,
    create_snapshot,
    verify_snapshot,
)


def _history(ticker: str, *, start: date, end: date) -> pd.DataFrame:
    assert start == date(2012, 1, 3)
    assert end == date(2026, 7, 18)
    dates = ["2018-06-19", "2026-07-17"] if ticker == "XLC" else ["2012-01-03", "2026-07-17"]
    return pd.DataFrame({
        "Date": dates,
        "Open": [100.0, 110.0], "High": [102.0, 112.0],
        "Low": [99.0, 109.0], "Close": [101.0, 111.0],
        "Adj Close": [95.0, 111.0], "Volume": [1000, 1100],
        "Dividends": [0.0, 0.5], "Stock Splits": [0.0, 2.0],
    })


def test_snapshot_preserves_actions_and_does_not_backfill_late_sector_etf():
    with TemporaryDirectory() as directory:
        snapshot = create_snapshot(
            "long-test-001", start=date(2012, 1, 3), end=date(2026, 7, 18),
            equities=["AAA"], sector_etfs=["XLC"], root=Path(directory),
            collector=_history,
            created_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
        )
        manifest = verify_snapshot(snapshot)
        assert manifest["files"]["AAA"]["dividend_events"] == 1
        assert manifest["files"]["AAA"]["split_events"] == 1
        assert manifest["files"]["XLC"]["start"] == "2018-06-19"
        assert manifest["policy"]["sector_etf_pre_inception_backfill"] is False
        assert manifest["policy"]["survivorship_safe"] is False


def test_snapshot_requires_fourteen_year_window():
    with TemporaryDirectory() as directory:
        with pytest.raises(LongPriceSnapshotError, match="14 calendar years"):
            create_snapshot(
                "too-short", start=date(2016, 1, 1), end=date(2026, 1, 1),
                equities=["AAA"], sector_etfs=["XLC"], root=Path(directory),
                collector=_history,
            )


def test_snapshot_fails_closed_if_sector_etf_is_missing():
    def failing(ticker: str, *, start: date, end: date) -> pd.DataFrame:
        if ticker == "XLC":
            raise RuntimeError("missing")
        return _history(ticker, start=start, end=end)

    with TemporaryDirectory() as directory:
        with pytest.raises(LongPriceSnapshotError, match="sector"):
            create_snapshot(
                "missing-sector", start=date(2012, 1, 3), end=date(2026, 7, 18),
                equities=["AAA"], sector_etfs=["XLC"], root=Path(directory),
                collector=failing,
            )
