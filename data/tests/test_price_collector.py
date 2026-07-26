import pandas as pd

from collectors.price_collector import _latest_regular_close


def test_uses_prior_session_when_daily_series_contains_current_session():
    closes = pd.Series(
        [319.69, 313.03],
        index=pd.to_datetime(["2026-07-23", "2026-07-24"]),
    )

    result = _latest_regular_close(
        closes,
        current_price=311.38,
        latest_ts=pd.Timestamp("2026-07-24 19:59", tz="America/New_York"),
    )

    assert result == 319.69


def test_uses_latest_daily_close_during_next_session_premarket():
    closes = pd.Series(
        [319.69, 313.03],
        index=pd.to_datetime(["2026-07-23", "2026-07-24"]),
    )

    result = _latest_regular_close(
        closes,
        current_price=314.0,
        latest_ts=pd.Timestamp("2026-07-27 08:00", tz="America/New_York"),
    )

    assert result == 313.03
