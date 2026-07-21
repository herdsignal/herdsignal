"""완료 주봉의 모든 Rush episode를 추출하고 126거래일 경로를 분류한다."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

from herd.validation_universe import TICKER_SECTOR_ETF
from herd.weekly_rsi_events import completed_weekly_bars, wilder_rsi


PROTOCOL_PATH = Path(__file__).with_name("rush_episode_protocol_v2.json")
CONTEXT_ONLY = {"SPY", "QQQ", "DIA", "IWM"}


def load_protocol(path: Path = PROTOCOL_PATH) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("protocol_version") != "HERD_RUSH_EPISODE_V2" \
            or protocol.get("status") != "LOCKED_BEFORE_EPISODE_EXTRACTION":
        raise ValueError("Rush episode protocol is not locked")
    if protocol["outcome"].get("unresolved_is_not_continuation") is not True:
        raise ValueError("unresolved paths must fail closed")
    return protocol


def _weekly_observations(frame: pd.DataFrame, protocol: dict) -> pd.DataFrame:
    weekly = completed_weekly_bars(frame)
    close = weekly["Adj Close"].astype(float)
    daily = frame.sort_values("Date").set_index("Date")["Adj Close"].astype(float)
    votes = protocol["observation"]["extension_votes"]
    weekly["weekly_rsi_14"] = wilder_rsi(close, 14)
    weekly["high_52w_proximity"] = close / close.rolling(52, min_periods=52).max()
    weekly["return_26w"] = close.pct_change(26, fill_method=None)
    sma200 = daily.rolling(200, min_periods=200).mean()
    sessions = pd.DatetimeIndex(pd.to_datetime(weekly["last_session"]))
    session_close = daily.reindex(sessions, method="ffill").to_numpy()
    session_sma200 = sma200.reindex(sessions, method="ffill").to_numpy()
    weekly["close_to_sma200"] = session_close / session_sma200
    weekly["rsi_vote"] = weekly["weekly_rsi_14"] >= votes["weekly_wilder_rsi_14"]
    weekly["high_vote"] = weekly["high_52w_proximity"] >= votes["adjusted_close_to_52_week_high_minimum"]
    weekly["return_vote"] = weekly["return_26w"] >= votes["adjusted_26_week_return_minimum"]
    weekly["sma_vote"] = weekly["close_to_sma200"] >= votes["adjusted_close_to_sma_200_minimum"]
    weekly["extension_votes"] = weekly[["rsi_vote", "high_vote", "return_vote", "sma_vote"]].sum(axis=1)
    return weekly


def extract_episodes(ticker: str, weekly: pd.DataFrame, protocol: dict) -> pd.DataFrame:
    observation = protocol["observation"]
    active = False
    reset_run = 0
    episode = 0
    rows = []
    for date, row in weekly.iterrows():
        vote_count = int(row["extension_votes"])
        if not active and vote_count >= observation["minimum_extension_votes"]:
            episode += 1
            active = True
            reset_run = 0
            rows.append({
                "ticker": ticker,
                "episode_id": f"{ticker}-R{episode:03d}",
                "signal_date": pd.Timestamp(date),
                "last_observed_session": pd.Timestamp(row["last_session"]),
                "signal_price": float(row["Adj Close"]),
                "extension_votes": vote_count,
                "weekly_rsi_14": float(row["weekly_rsi_14"]),
                "high_52w_proximity": float(row["high_52w_proximity"]),
                "return_26w": float(row["return_26w"]),
                "close_to_sma200": float(row["close_to_sma200"]),
            })
        elif active:
            reset_run = reset_run + 1 if vote_count <= observation["episode_reset_maximum_votes"] else 0
            if reset_run >= observation["episode_reset_consecutive_weeks"]:
                active = False
                reset_run = 0
    return pd.DataFrame(rows)


def classify_path(close: pd.Series, event: pd.Series, protocol: dict) -> dict | None:
    close = close.dropna().sort_index()
    signal = pd.Timestamp(event["last_observed_session"])
    position = close.index.searchsorted(signal, side="right") - 1
    horizon = protocol["outcome"]["horizon_sessions"]
    if position < 0 or position + horizon >= len(close):
        return None
    start = float(close.iloc[position])
    path = close.iloc[position + 1:position + horizon + 1]
    returns = path / start - 1
    mae, mfe, terminal = float(returns.min()), float(returns.max()), float(returns.iloc[-1])
    low_date, high_date = returns.idxmin(), returns.idxmax()
    outcome = protocol["outcome"]
    pullback_date = returns[returns <= outcome["temporary_pullback"]["minimum_adverse_return"]].index.min() \
        if (returns <= outcome["temporary_pullback"]["minimum_adverse_return"]).any() else pd.NaT
    advance_date = returns[returns >= outcome["continuation"]["minimum_favorable_return"]].index.min() \
        if (returns >= outcome["continuation"]["minimum_favorable_return"]).any() else pd.NaT
    recovered = bool(returns.loc[low_date:].max() >= outcome["temporary_pullback"]["recovery_floor"])
    if mae <= outcome["structural_break"]["minimum_adverse_return"] \
            and terminal <= outcome["structural_break"]["terminal_return_maximum"]:
        label = "STRUCTURAL_BREAK"
    elif mae <= outcome["large_pullback"]["minimum_adverse_return"]:
        label = "LARGE_PULLBACK"
    elif mae <= outcome["temporary_pullback"]["minimum_adverse_return"] and recovered:
        label = "TEMPORARY_PULLBACK"
    elif pd.notna(advance_date) and (pd.isna(pullback_date) or advance_date < pullback_date) \
            and terminal > outcome["continuation"]["terminal_return_minimum"]:
        label = "CONTINUATION"
    else:
        label = "UNRESOLVED"
    return {
        "path_label": label,
        "mae_126d": mae,
        "mfe_126d": mfe,
        "terminal_return_126d": terminal,
        "low_before_high": bool(low_date < high_date),
        "recovered_after_low": recovered,
        "time_to_low_sessions": int(close.index.get_loc(low_date) - position),
        "time_to_high_sessions": int(close.index.get_loc(high_date) - position),
        "outcome_end": path.index[-1],
    }


def build_episode_paths(frames: dict[str, pd.DataFrame], protocol: dict) -> pd.DataFrame:
    parts = []
    for ticker in sorted(set(TICKER_SECTOR_ETF) - CONTEXT_ONLY):
        episodes = extract_episodes(ticker, _weekly_observations(frames[ticker], protocol), protocol)
        close = frames[ticker].sort_values("Date").set_index("Date")["Adj Close"]
        for _, event in episodes.iterrows():
            outcome = classify_path(close, event, protocol)
            if outcome is not None:
                parts.append(event.to_dict() | outcome)
    return pd.DataFrame(parts)


def summarize(paths: pd.DataFrame) -> dict:
    counts = paths["path_label"].value_counts().to_dict() if not paths.empty else {}
    return {
        "report_version": "herd-rush-episode-study-v2",
        "status": "DESCRIPTIVE_ONLY_NO_ACTION_AUTHORITY",
        "episodes": len(paths),
        "equity_tickers": int(paths["ticker"].nunique()) if not paths.empty else 0,
        "label_counts": counts,
        "resolved_target_episodes": int(len(paths) - counts.get("UNRESOLVED", 0)),
        "survivorship_safe": False,
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
    }


def _load_frames(snapshot: Path) -> dict[str, pd.DataFrame]:
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    frames = {}
    for ticker, item in manifest["files"].items():
        with gzip.open(snapshot / item["path"], "rt", encoding="utf-8") as stream:
            frames[ticker] = pd.read_csv(stream, parse_dates=["Date"])
    return frames


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    paths = build_episode_paths(_load_frames(args.snapshot), load_protocol())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    paths.to_csv(args.output, index=False)
    report = summarize(paths)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
