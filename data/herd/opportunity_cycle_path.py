"""기존 후보 이후 경로를 continuation/pullback/break/noise로 진단한다."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd


TARGET_PATH = Path(__file__).with_name("opportunity_cycle_target_v1.json")


class OpportunityCycleTargetError(ValueError):
    pass


def load_target(path: Path = TARGET_PATH) -> tuple[dict, dict]:
    target = json.loads(path.read_text(encoding="utf-8"))
    if target.get("target_version") != "HERD_OPPORTUNITY_CYCLE_TARGET_V1" \
            or target.get("status") != "LOCKED_BEFORE_PATH_DIAGNOSTIC_RESULTS":
        raise OpportunityCycleTargetError("opportunity target is not locked")
    if target.get("path_horizon_days") != 126 \
            or target.get("interpretation", {}).get("oracle_reentry_is_not_executable") is not True:
        raise OpportunityCycleTargetError("unsafe path target")
    if "USE_FUTURE_PATH_AS_FEATURE" not in target.get("forbidden", []):
        raise OpportunityCycleTargetError("future path leakage is not forbidden")
    return target, {"target_version": target["target_version"], "locked": True}


def _thresholds(volatility: float) -> tuple[float, float, float]:
    pullback = max(0.05, 1.5 * volatility * np.sqrt(21 / 252))
    continuation = max(0.08, 1.5 * volatility * np.sqrt(63 / 252))
    structural = max(0.15, 2.5 * volatility * np.sqrt(63 / 252))
    return pullback, continuation, structural


def diagnose_path(close: pd.Series, signal_date: pd.Timestamp, target: dict) -> dict | None:
    close = close.dropna().sort_index()
    position = close.index.searchsorted(signal_date, side="right") - 1
    horizon = target["path_horizon_days"]
    if position < target["signal_volatility_window_days"] or position + horizon >= len(close):
        return None
    history = close.iloc[position - target["signal_volatility_window_days"]:position + 1]
    volatility = float(history.pct_change(fill_method=None).std(ddof=1) * np.sqrt(252))
    if not np.isfinite(volatility) or volatility <= 0:
        return None
    start = float(close.iloc[position])
    path = close.iloc[position + 1:position + horizon + 1]
    returns = path / start - 1
    high_date = returns.idxmax()
    low_date = returns.idxmin()
    mfe = float(returns.max())
    mae = float(returns.min())
    terminal = float(returns.iloc[-1])
    pullback, continuation, structural = _thresholds(volatility)
    after_low = returns.loc[low_date:]
    recovered = bool(not after_low.empty and after_low.max() >= target["volatility_scaled_thresholds"]["recovery_floor"])
    pullback_date = returns[returns <= -pullback].index.min() if (returns <= -pullback).any() else pd.NaT
    advance_date = returns[returns >= continuation].index.min() if (returns >= continuation).any() else pd.NaT
    if mae <= -structural and terminal <= target["volatility_scaled_thresholds"]["structural_terminal_ceiling"]:
        label = "STRUCTURAL_BREAK"
    elif pd.notna(pullback_date) and recovered:
        label = "TRADABLE_PULLBACK"
    elif pd.notna(advance_date) and (pd.isna(pullback_date) or advance_date < pullback_date) and terminal > 0:
        label = "CONTINUATION"
    else:
        label = "NOISE"
    return {
        "label": label,
        "signal_price": start,
        "signal_volatility": volatility,
        "pullback_threshold": pullback,
        "continuation_threshold": continuation,
        "structural_threshold": structural,
        "mfe": mfe,
        "mae": mae,
        "time_to_high_days": int(close.index.get_loc(high_date) - position),
        "time_to_low_days": int(close.index.get_loc(low_date) - position),
        "low_before_high": bool(low_date < high_date),
        "recovery_after_low": recovered,
        "terminal_return": terminal,
        "gross_oracle_opportunity": float(start / float(path.min()) - 1),
        "outcome_end": path.index[-1],
    }


def diagnose_events(events: pd.DataFrame, prices: dict[str, pd.Series], target: dict) -> pd.DataFrame:
    source = events[(events["group"] == "TREATMENT") & (events["horizon_days"] == 126)].copy()
    source["signal_date"] = pd.to_datetime(source["signal_date"])
    rows = []
    keys = ["ticker", "hypothesis_id", "threshold", "signal_date", "fold_id"]
    for event in source.drop_duplicates(keys).itertuples(index=False):
        result = diagnose_path(prices[event.ticker], event.signal_date, target)
        if result is not None:
            rows.append({key: getattr(event, key) for key in keys} | result)
    return pd.DataFrame(rows)


def summarize_paths(paths: pd.DataFrame) -> dict:
    label_counts = paths["label"].value_counts().to_dict() if not paths.empty else {}
    family = (
        paths.groupby(["hypothesis_id", "label"]).size().unstack(fill_value=0).to_dict("index")
        if not paths.empty else {}
    )
    return {
        "report_version": "herd-opportunity-cycle-path-v1",
        "events": len(paths),
        "tickers": paths["ticker"].nunique() if not paths.empty else 0,
        "folds": paths["fold_id"].nunique() if not paths.empty else 0,
        "label_counts": label_counts,
        "hypothesis_label_counts": family,
        "labels_authorize_actions": False,
        "oracle_reentry_executable": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--paths-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()
    target, audit = load_target()
    manifest = json.loads((args.snapshot / "manifest.json").read_text(encoding="utf-8"))
    prices = {}
    for ticker, item in manifest["files"].items():
        if item["role"] != "EQUITY":
            continue
        with gzip.open(args.snapshot / item["path"], "rt", encoding="utf-8") as stream:
            frame = pd.read_csv(stream, parse_dates=["Date"])
        prices[ticker] = frame.set_index("Date")["Adj Close"]
    paths = diagnose_events(pd.read_csv(args.events), prices, target)
    report = summarize_paths(paths) | {"target": audit}
    args.paths_output.parent.mkdir(parents=True, exist_ok=True)
    paths.to_csv(args.paths_output, index=False)
    args.report_output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
