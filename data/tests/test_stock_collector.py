from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from collectors import stock_collector


def _raw_frame(*, close: float | None = 101.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [100.0],
            "High": [102.0],
            "Low": [99.0],
            "Close": [close],
            "Volume": [1_000.0],
        },
        index=pd.DatetimeIndex(["2026-07-24"], name="Date"),
    )


def test_collect_retries_incomplete_ohlcv(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter([_raw_frame(close=None), _raw_frame()])
    sleeps: list[int] = []
    monkeypatch.setattr(stock_collector, "_fetch_raw", lambda *_: next(responses))
    monkeypatch.setattr(stock_collector.time, "sleep", sleeps.append)

    result = stock_collector.collect("SPY")

    assert result.iloc[0]["Close"] == 101.0
    assert sleeps == [stock_collector.RETRY_DELAY_SEC]


def test_collect_fails_after_repeated_incomplete_ohlcv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        stock_collector,
        "_fetch_raw",
        lambda *_: _raw_frame(close=None),
    )
    monkeypatch.setattr(stock_collector.time, "sleep", lambda *_: None)

    with pytest.raises(RuntimeError, match="데이터 수집 실패"):
        stock_collector.collect("SPY")


def test_drops_current_daily_bar_before_us_market_close() -> None:
    frame = pd.DataFrame(
        {
            "Date": [datetime(2026, 7, 24).date(), datetime(2026, 7, 27).date()],
            "Open": [100.0, 102.0],
            "High": [102.0, 103.0],
            "Low": [99.0, 102.5],
            "Close": [101.0, 102.8],
            "Volume": [1_000.0, 200.0],
        }
    )

    result = stock_collector._drop_incomplete_market_session(
        frame,
        now=datetime(2026, 7, 27, 13, 0, tzinfo=ZoneInfo("America/New_York")),
    )

    assert result["Date"].tolist() == [datetime(2026, 7, 24).date()]


def test_keeps_current_daily_bar_after_completion_cutoff() -> None:
    frame = pd.DataFrame(
        {
            "Date": [datetime(2026, 7, 27).date()],
            "Open": [100.0],
            "High": [102.0],
            "Low": [99.0],
            "Close": [101.0],
            "Volume": [1_000.0],
        }
    )

    result = stock_collector._drop_incomplete_market_session(
        frame,
        now=datetime(2026, 7, 27, 16, 30, tzinfo=ZoneInfo("America/New_York")),
    )

    assert result.equals(frame)
