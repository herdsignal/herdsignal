import numpy as np
import pandas as pd

from herd.weekly_rsi_events import completed_weekly_bars, extract_weekly_rsi_events, load_protocol, wilder_rsi


def _daily_frame(weeks=60):
    dates = pd.bdate_range("2020-01-06", periods=weeks * 5)
    close = np.linspace(50, 100, len(dates))
    return pd.DataFrame({
        "Date": dates, "Open": close * 0.99, "High": close * 1.01,
        "Low": close * 0.98, "Close": close, "Adj Close": close, "Volume": 1000,
    })


def test_incomplete_week_is_not_observable():
    frame = _daily_frame(20)
    as_of = pd.Timestamp("2020-03-11")
    weekly = completed_weekly_bars(frame, as_of)
    assert (weekly.index.dayofweek == 4).all()
    assert (weekly.index <= as_of).all()


def test_future_prices_do_not_change_past_events():
    protocol, _ = load_protocol()
    frame = _daily_frame()
    signal = frame["Date"].iloc[220]
    first = extract_weekly_rsi_events(frame[frame["Date"] <= signal], "TEST", protocol)
    changed = frame.copy()
    changed.loc[changed["Date"] > signal, "Adj Close"] *= 0.1
    second = extract_weekly_rsi_events(changed[changed["Date"] <= signal], "TEST", protocol)
    pd.testing.assert_frame_equal(first.reset_index(drop=True), second.reset_index(drop=True))


def test_wilder_rsi_reaches_extreme_in_persistent_rise():
    close = pd.Series(np.r_[np.linspace(100, 95, 15), np.linspace(96, 150, 20)])
    assert wilder_rsi(close, 14).iloc[-1] > 75


def test_protocol_keeps_events_research_only_and_sparse():
    protocol, audit = load_protocol()
    assert audit["locked"] is True
    assert protocol["default_action"] == "HOLD"
    assert protocol["research_frequency_bounds"]["profit_take_candidates_per_ticker_year_maximum"] == 2.0
    assert protocol["research_only"]["operational_action_ratio"] == 0.0


def test_crossing_80_does_not_start_a_second_episode():
    protocol, _ = load_protocol()
    weekly_close = np.r_[np.linspace(100, 85, 18), np.linspace(86, 150, 25)]
    close = np.repeat(weekly_close, 5)
    dates = pd.bdate_range("2020-01-06", periods=len(close))
    frame = pd.DataFrame({
        "Date": dates, "Open": close, "High": close, "Low": close,
        "Close": close, "Adj Close": close, "Volume": 1000,
    })
    events = extract_weekly_rsi_events(frame, "TEST", protocol)
    assert len(events[events["event_type"] == "EXTREME_ENTRY"]) == 1
    assert len(events[events["event_type"] == "EXTREME_ESCALATION"]) == 1
