"""빠른·느린 주봉 추세의 격차와 전환 속도를 재진입 가치 목표에 독립 비교한다."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

from herd.reentry_feature_discovery_v1 import compare
from herd.weekly_rsi_events import completed_weekly_bars


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json")
FEATURES = ["FAST_SLOW_TREND_GAP", "FAST_SLOW_TRANSITION_VELOCITY_4W"]


def load_protocol(path: Path = PROTOCOL_PATH) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_FEATURE_RESULTS":
        raise ValueError("fast/slow transition protocol must be locked")
    if [row["id"] for row in protocol["candidate_features"]] != FEATURES:
        raise ValueError("fast/slow candidate set changed")
    return protocol


def _annualized_log_slope(values: np.ndarray) -> float:
    if len(values) < 2 or np.any(~np.isfinite(values)) or np.any(values <= 0):
        return np.nan
    return float(np.polyfit(np.arange(len(values)), np.log(values), 1)[0] * 52.0)


def weekly_features(frame: pd.DataFrame, protocol: dict) -> pd.DataFrame:
    weekly = completed_weekly_bars(frame).copy()
    close = weekly["Adj Close"].astype(float)
    fast = protocol["fast_slope_weeks"] + 1
    slow = protocol["slow_slope_weeks"] + 1
    volatility = np.log(close).diff().rolling(protocol["normalization_volatility_weeks"]).std() * np.sqrt(52)
    fast_slope = close.rolling(fast).apply(_annualized_log_slope, raw=True)
    slow_slope = close.rolling(slow).apply(_annualized_log_slope, raw=True)
    gap = (fast_slope - slow_slope) / volatility.replace(0, np.nan)
    result = pd.DataFrame({
        "last_observed_session": pd.to_datetime(weekly["last_session"]),
        FEATURES[0]: gap,
        FEATURES[1]: gap.diff(protocol["velocity_lag_weeks"]),
    }).dropna(subset=["last_observed_session"])
    return result.sort_values("last_observed_session")


def attach_features(targets: pd.DataFrame, snapshot: Path, protocol: dict) -> pd.DataFrame:
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    groups = []
    for ticker, events in targets.groupby("ticker", sort=True):
        item = manifest["files"].get(ticker)
        if not item or item.get("role") != "EQUITY":
            missing = events.copy()
            for feature in FEATURES:
                missing[feature] = np.nan
            groups.append(missing)
            continue
        with gzip.open(snapshot / item["path"], "rt", encoding="utf-8") as stream:
            frame = pd.read_csv(stream, parse_dates=["Date"])
        right = weekly_features(frame, protocol)
        left = events.copy().sort_values("signal_date")
        left["signal_date"] = pd.to_datetime(left["signal_date"])
        merged = pd.merge_asof(
            left, right, left_on="signal_date", right_on="last_observed_session",
            direction="backward", allow_exact_matches=True,
        )
        if (merged["last_observed_session"] > merged["signal_date"]).any():
            raise ValueError("post-signal weekly bar leaked into features")
        groups.append(merged)
    return pd.concat(groups, ignore_index=True)


def evaluate(panel: pd.DataFrame, protocol: dict) -> pd.DataFrame:
    adapter = {
        "candidate_features": protocol["candidate_features"],
        "comparison": protocol["comparison"],
        "retention_gate": {
            **protocol["retention_gate"],
            "minimum_absolute_rank_biserial": protocol["retention_gate"]["minimum_directional_rank_biserial"],
        },
    }
    table = compare(panel, adapter)
    expected = {row["id"]: row["expected_direction"] for row in protocol["candidate_features"]}
    table["expected_direction"] = table["feature"].map(expected)
    table["direction_matched"] = table["rank_biserial"] <= -protocol["retention_gate"]["minimum_directional_rank_biserial"]
    table["retained_for_new_sample_preregistration"] &= table["direction_matched"]
    return table


def run(protocol_path: Path = PROTOCOL_PATH) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    protocol = load_protocol(protocol_path)
    target_report = json.loads((ROOT / protocol["target_report"]).read_text(encoding="utf-8"))
    if target_report.get("status") != "DISCOVERY_TARGET_READY":
        raise ValueError("reentry target is not ready")
    targets = pd.read_csv(ROOT / protocol["target_rows"])
    panel = attach_features(targets, ROOT / protocol["snapshot"], protocol)
    comparison = evaluate(panel, protocol)
    retained = comparison.loc[comparison["retained_for_new_sample_preregistration"], "feature"].tolist()
    report = {
        "report_version": "HERD_FAST_SLOW_TRANSITION_V1",
        "status": "DISCOVERY_COMPLETE",
        "target_events": int(len(panel)),
        "features_compared": len(FEATURES),
        "retained_features": retained,
        "independent_oos_passed_features": [],
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
    }
    return panel, comparison, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    panel, comparison, report = run()
    args.panel.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.panel, index=False)
    comparison.to_json(args.comparison, orient="records", indent=2)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
