"""주봉 RSI 사건 이후 4·8·13·26주 가격 경로를 기술적으로 측정한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from herd.weekly_rsi_events import completed_weekly_bars, load_snapshot_frames


MEASUREMENT_PATH = Path(__file__).with_name("weekly_rsi_path_measurement_v1.json")


def load_measurement(path: Path = MEASUREMENT_PATH) -> tuple[dict, dict]:
    measurement = json.loads(path.read_text(encoding="utf-8"))
    if measurement.get("measurement_version") != "HERD_WEEKLY_RSI_PATH_MEASUREMENT_V1" \
            or measurement.get("status") != "LOCKED_BEFORE_FORWARD_PATH_RESULTS":
        raise ValueError("weekly RSI path measurement is not locked")
    if measurement.get("horizons_weeks") != [4, 8, 13, 26] \
            or measurement.get("availability") != "FUTURE_PATH_IS_OUTCOME_ONLY":
        raise ValueError("weekly RSI path measurement was weakened")
    return measurement, {"measurement_version": measurement["measurement_version"], "locked": True}


def measure_event_path(weekly: pd.DataFrame, event_date: pd.Timestamp, horizons: list[int]) -> dict | None:
    weekly = weekly.sort_index()
    location = weekly.index.searchsorted(pd.Timestamp(event_date), side="right") - 1
    if location < 0 or location + max(horizons) >= len(weekly):
        return None
    start = float(weekly["Adj Close"].iloc[location])
    outcomes: dict[str, float | int | bool] = {}
    for horizon in horizons:
        path = weekly["Adj Close"].iloc[location + 1:location + horizon + 1].astype(float)
        relative = path / start - 1
        running_peak = pd.concat([pd.Series([start]), path.reset_index(drop=True)]).cummax().iloc[1:]
        drawdown = path.reset_index(drop=True) / running_peak.to_numpy() - 1
        prefix = f"h{horizon}w"
        outcomes[f"{prefix}_forward_return"] = float(relative.iloc[-1])
        outcomes[f"{prefix}_maximum_advance"] = float(relative.max())
        outcomes[f"{prefix}_maximum_decline"] = float(relative.min())
        outcomes[f"{prefix}_maximum_interim_drawdown"] = float(drawdown.min())
        outcomes[f"{prefix}_weeks_below_event_close"] = int((relative < 0).sum())
        for threshold in (2, 5, 10):
            outcomes[f"{prefix}_decline_at_least_{threshold}pct"] = bool(relative.min() <= -threshold / 100)
    return outcomes


def measure_paths(events: pd.DataFrame, frames: dict[str, pd.DataFrame], measurement: dict) -> pd.DataFrame:
    weekly = {ticker: completed_weekly_bars(frame) for ticker, frame in frames.items()}
    rows = []
    for event in events.itertuples(index=False):
        result = measure_event_path(weekly[event.ticker], pd.Timestamp(event.event_date), measurement["horizons_weeks"])
        if result is not None:
            rows.append(event._asdict() | result)
    return pd.DataFrame(rows)


def summarize_paths(paths: pd.DataFrame, measurement: dict) -> dict:
    summaries = {}
    for event_type, rows in paths.groupby("event_type"):
        horizons = {}
        for horizon in measurement["horizons_weeks"]:
            prefix = f"h{horizon}w"
            horizons[str(horizon)] = {
                "events": len(rows),
                "median_forward_return": float(rows[f"{prefix}_forward_return"].median()),
                "median_maximum_advance": float(rows[f"{prefix}_maximum_advance"].median()),
                "median_maximum_decline": float(rows[f"{prefix}_maximum_decline"].median()),
                "median_maximum_interim_drawdown": float(rows[f"{prefix}_maximum_interim_drawdown"].median()),
                "decline_at_least_2pct_rate": float(rows[f"{prefix}_decline_at_least_2pct"].mean()),
                "decline_at_least_5pct_rate": float(rows[f"{prefix}_decline_at_least_5pct"].mean()),
                "decline_at_least_10pct_rate": float(rows[f"{prefix}_decline_at_least_10pct"].mean())
            }
        summaries[event_type] = horizons
    return {
        "report_version": "herd-weekly-rsi-path-diagnostic-v1",
        "events_with_complete_26w_path": len(paths),
        "tickers": int(paths["ticker"].nunique()) if not paths.empty else 0,
        "event_types": summaries,
        "descriptive_only": True,
        "events_authorize_actions": False,
        "operational_action_ratio": 0.0
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--paths", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    measurement, _ = load_measurement()
    paths = measure_paths(pd.read_csv(args.events), load_snapshot_frames(args.snapshot), measurement)
    report = summarize_paths(paths, measurement)
    args.paths.parent.mkdir(parents=True, exist_ok=True)
    paths.to_csv(args.paths, index=False)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
