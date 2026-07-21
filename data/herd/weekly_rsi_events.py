"""완료된 주봉으로 희소 RSI 극단·둔화·냉각 사건을 추출한다."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd


PROTOCOL_PATH = Path(__file__).with_name("sparse_action_protocol_v1.json")
EVENT_COLUMNS = [
    "ticker", "event_date", "last_observed_session", "event_type", "entry_level",
    "episode_start", "weekly_rsi", "adjusted_close"
]


def load_protocol(path: Path = PROTOCOL_PATH) -> tuple[dict, dict]:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("protocol_version") != "HERD_SPARSE_ACTION_PROTOCOL_V1" \
            or protocol.get("status") != "LOCKED_BEFORE_WEEKLY_RSI_RESULTS":
        raise ValueError("sparse action protocol is not locked")
    sampling = protocol["weekly_sampling"]
    if sampling["rsi_method"] != "WILDER" or sampling["outcome_horizons_weeks"] != [4, 8, 13, 26]:
        raise ValueError("weekly RSI protocol was weakened")
    if protocol["research_only"]["events_do_not_authorize_actions"] is not True:
        raise ValueError("weekly RSI events cannot authorize actions")
    return protocol, {"protocol_version": protocol["protocol_version"], "locked": True}


def wilder_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    values = close.astype(float)
    delta = values.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    average_gain = pd.Series(np.nan, index=values.index, dtype=float)
    average_loss = pd.Series(np.nan, index=values.index, dtype=float)
    if len(values) <= period:
        return average_gain
    average_gain.iloc[period] = gains.iloc[1:period + 1].mean()
    average_loss.iloc[period] = losses.iloc[1:period + 1].mean()
    for index in range(period + 1, len(values)):
        average_gain.iloc[index] = ((period - 1) * average_gain.iloc[index - 1] + gains.iloc[index]) / period
        average_loss.iloc[index] = ((period - 1) * average_loss.iloc[index - 1] + losses.iloc[index]) / period
    strength = average_gain / average_loss.replace(0, np.nan)
    result = 100 - 100 / (1 + strength)
    result[(average_loss == 0) & (average_gain > 0)] = 100.0
    result[(average_loss == 0) & (average_gain == 0)] = 50.0
    return result


def completed_weekly_bars(frame: pd.DataFrame, as_of: pd.Timestamp | None = None) -> pd.DataFrame:
    source = frame.copy()
    source["Date"] = pd.to_datetime(source["Date"])
    if as_of is not None:
        source = source[source["Date"] <= pd.Timestamp(as_of)]
    source = source.sort_values("Date").set_index("Date")
    weekly = source.resample("W-FRI", label="right", closed="right").agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last",
        "Adj Close": "last", "Volume": "sum"
    }).dropna(subset=["Adj Close"])
    last_sessions = source["Adj Close"].resample("W-FRI", label="right", closed="right").apply(
        lambda values: values.index.max() if len(values) else pd.NaT
    )
    weekly["last_session"] = pd.to_datetime(last_sessions.reindex(weekly.index))
    if as_of is not None:
        # A Friday-labelled bar is not complete before that week's Friday close.
        weekly = weekly[weekly.index <= pd.Timestamp(as_of).normalize()]
    return weekly


def extract_weekly_rsi_events(frame: pd.DataFrame, ticker: str, protocol: dict) -> pd.DataFrame:
    weekly = completed_weekly_bars(frame)
    sampling = protocol["weekly_sampling"]
    weekly["weekly_rsi"] = wilder_rsi(weekly["Adj Close"], sampling["rsi_period_weeks"])
    levels = sampling["extreme_entry_levels"]
    cooling = sampling["cooling_level"]
    rows: list[dict] = []
    active_level: int | None = None
    active_since: pd.Timestamp | None = None
    persistent_emitted = False
    deceleration_emitted = False
    for index in range(1, len(weekly)):
        current = weekly.iloc[index]
        previous = weekly.iloc[index - 1]
        date = weekly.index[index]
        entry_level, escalation_level = levels
        if active_level is None and previous["weekly_rsi"] < entry_level <= current["weekly_rsi"]:
            active_level = entry_level
            active_since = date
            persistent_emitted = False
            deceleration_emitted = False
            rows.append(_event_row(ticker, weekly, index, "EXTREME_ENTRY", active_level, active_since))
        elif active_level is not None:
            if active_level < escalation_level and previous["weekly_rsi"] < escalation_level <= current["weekly_rsi"]:
                active_level = escalation_level
                rows.append(_event_row(ticker, weekly, index, "EXTREME_ESCALATION", active_level, active_since))
            duration = int((weekly.index.get_loc(date) - weekly.index.get_loc(active_since)) + 1)
            if not persistent_emitted and duration >= sampling["minimum_extreme_duration_weeks"] \
                    and current["weekly_rsi"] >= active_level:
                rows.append(_event_row(ticker, weekly, index, "EXTREME_PERSISTENCE", active_level, active_since))
                persistent_emitted = True
            if index >= 2 and not deceleration_emitted \
                    and weekly["weekly_rsi"].iloc[index] < weekly["weekly_rsi"].iloc[index - 1] \
                    < weekly["weekly_rsi"].iloc[index - 2]:
                rows.append(_event_row(ticker, weekly, index, "EXTREME_DECELERATION", active_level, active_since))
                deceleration_emitted = True
            if previous["weekly_rsi"] >= cooling > current["weekly_rsi"]:
                rows.append(_event_row(ticker, weekly, index, "COOLING_EXIT", active_level, active_since))
                active_level = None
                active_since = None
    return pd.DataFrame(rows, columns=EVENT_COLUMNS)


def _event_row(
    ticker: str,
    weekly: pd.DataFrame,
    index: int,
    event_type: str,
    entry_level: int,
    episode_start: pd.Timestamp,
) -> dict:
    row = weekly.iloc[index]
    return {
        "ticker": ticker,
        "event_date": weekly.index[index],
        "last_observed_session": row["last_session"],
        "event_type": event_type,
        "entry_level": entry_level,
        "episode_start": episode_start,
        "weekly_rsi": float(row["weekly_rsi"]),
        "adjusted_close": float(row["Adj Close"]),
    }


def load_snapshot_frames(snapshot: Path) -> dict[str, pd.DataFrame]:
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    frames = {}
    for ticker, item in manifest["files"].items():
        if item["role"] != "EQUITY":
            continue
        with gzip.open(snapshot / item["path"], "rt", encoding="utf-8") as stream:
            frames[ticker] = pd.read_csv(stream, parse_dates=["Date"])
    return frames


def summarize_events(events: pd.DataFrame, frames: dict[str, pd.DataFrame], protocol: dict) -> dict:
    years = {}
    for ticker, frame in frames.items():
        span = (frame["Date"].max() - frame["Date"].min()).days / 365.2425
        years[ticker] = max(span, 1 / 52)
    entries = events[events["event_type"] == "EXTREME_ENTRY"] if not events.empty else events
    annual_rates = entries.groupby("ticker").size().div(pd.Series(years)).fillna(0)
    maximum = protocol["research_frequency_bounds"]["profit_take_candidates_per_ticker_year_maximum"]
    return {
        "report_version": "herd-weekly-rsi-event-frequency-v1",
        "events": len(events),
        "extreme_entries": len(entries),
        "tickers": len(frames),
        "event_type_counts": events["event_type"].value_counts().to_dict() if not events.empty else {},
        "median_extreme_entries_per_ticker_year": float(annual_rates.median()),
        "maximum_extreme_entries_per_ticker_year": float(annual_rates.max()),
        "tickers_above_frequency_diagnostic": sorted(annual_rates[annual_rates > maximum].index),
        "frequency_diagnostic_maximum": maximum,
        "events_authorize_actions": False,
        "operational_action_ratio": 0.0
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    protocol, _ = load_protocol()
    frames = load_snapshot_frames(args.snapshot)
    parts = [extract_weekly_rsi_events(frame, ticker, protocol) for ticker, frame in frames.items()]
    events = pd.concat([part for part in parts if not part.empty], ignore_index=True) if parts else pd.DataFrame()
    report = summarize_events(events, frames, protocol)
    args.events.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(args.events, index=False)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
