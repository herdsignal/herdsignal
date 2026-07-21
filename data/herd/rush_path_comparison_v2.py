"""Rush 경로 직전 관측값의 발견구간 효과 크기와 반복성을 비교한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu


PROTOCOL_PATH = Path(__file__).with_suffix(".json")


def load_protocol(path: Path = PROTOCOL_PATH) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("protocol_version") != "HERD_RUSH_PATH_COMPARISON_V2" \
            or protocol.get("status") != "LOCKED_BEFORE_PATH_FEATURE_COMPARISON":
        raise ValueError("Rush path comparison protocol is not locked")
    if "USE_CONFIRMATION_ROWS_FOR_FEATURE_RETENTION" not in protocol.get("forbidden", []):
        raise ValueError("confirmation leakage is not forbidden")
    return protocol


def attach_features(paths: pd.DataFrame, weekly_features: pd.DataFrame) -> pd.DataFrame:
    left = paths.copy()
    right = weekly_features.copy()
    left["signal_date"] = pd.to_datetime(left["signal_date"])
    right["signal_date"] = pd.to_datetime(right["signal_date"])
    duplicate = right.duplicated(["ticker", "signal_date"]).any()
    if duplicate:
        raise ValueError("weekly feature key is not unique")
    added = [column for column in right.columns if column not in left.columns and column not in {"last_observed_session"}]
    return left.merge(right[["ticker", "signal_date", *added]], on=["ticker", "signal_date"], how="left", validate="one_to_one")


def _rank_biserial(treatment: pd.Series, control: pd.Series) -> tuple[float, float]:
    result = mannwhitneyu(treatment, control, alternative="two-sided")
    effect = 2 * float(result.statistic) / (len(treatment) * len(control)) - 1
    return effect, float(result.pvalue)


def _holm(rows: list[dict]) -> None:
    ordered = sorted(range(len(rows)), key=lambda index: rows[index]["raw_p_value"])
    running = 0.0
    for rank, index in enumerate(ordered):
        running = max(running, min(1.0, rows[index]["raw_p_value"] * (len(rows) - rank)))
        rows[index]["holm_p_value"] = running


def compare_discovery(panel: pd.DataFrame, protocol: dict) -> pd.DataFrame:
    panel = panel.copy()
    panel["signal_date"] = pd.to_datetime(panel["signal_date"])
    discovery = panel[panel["signal_date"] <= pd.Timestamp(protocol["discovery_end"])].copy()
    comparison = protocol["primary_comparison"]
    gate = protocol["discovery_retention_gate"]
    period_cut = pd.Timestamp("2013-12-31")
    rows = []
    for feature in protocol["candidate_features"]:
        eligible = discovery[discovery["path_label"].isin(comparison["treatment_labels"] + comparison["control_labels"])]
        missing = float(eligible[feature].isna().mean()) if not eligible.empty else 1.0
        treatment = eligible[eligible["path_label"].isin(comparison["treatment_labels"])][feature].dropna()
        control = eligible[eligible["path_label"].isin(comparison["control_labels"])][feature].dropna()
        effect, p_value = _rank_biserial(treatment, control) if not treatment.empty and not control.empty else (np.nan, 1.0)
        half_effects = []
        for mask in (eligible["signal_date"] <= period_cut, eligible["signal_date"] > period_cut):
            half = eligible[mask]
            left = half[half["path_label"].isin(comparison["treatment_labels"])][feature].dropna()
            right = half[half["path_label"].isin(comparison["control_labels"])][feature].dropna()
            half_effects.append(_rank_biserial(left, right)[0] if len(left) >= 5 and len(right) >= 5 else np.nan)
        same_direction = sum(np.isfinite(value) and np.sign(value) == np.sign(effect) for value in half_effects)
        rows.append({
            "feature": feature,
            "treatment_events": len(treatment),
            "control_events": len(control),
            "missing_fraction": missing,
            "treatment_median": float(treatment.median()) if not treatment.empty else None,
            "control_median": float(control.median()) if not control.empty else None,
            "rank_biserial": effect,
            "raw_p_value": p_value,
            "first_half_effect": half_effects[0],
            "second_half_effect": half_effects[1],
            "same_direction_halves": same_direction,
        })
    _holm(rows)
    for row in rows:
        row["retained_for_preregistration"] = bool(
            row["treatment_events"] >= gate["minimum_treatment_events"]
            and row["control_events"] >= gate["minimum_control_events"]
            and row["missing_fraction"] <= gate["maximum_missing_fraction"]
            and abs(row["rank_biserial"]) >= gate["minimum_absolute_rank_biserial"]
            and row["holm_p_value"] <= gate["maximum_holm_p_value"]
            and row["same_direction_halves"] >= gate["minimum_same_direction_halves"]
        )
    return pd.DataFrame(rows)


def summarize(table: pd.DataFrame, panel: pd.DataFrame, protocol: dict) -> dict:
    retained = table[table["retained_for_preregistration"]]
    discovery = panel[pd.to_datetime(panel["signal_date"]) <= pd.Timestamp(protocol["discovery_end"])]
    return {
        "report_version": "herd-rush-path-comparison-v2",
        "status": "DISCOVERY_COMPARISON_COMPLETE",
        "discovery_episodes": len(discovery),
        "features_compared": len(table),
        "retained_features": retained["feature"].tolist(),
        "retained_count": len(retained),
        "confirmation_rows_accessed_for_selection": False,
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paths", type=Path, required=True)
    parser.add_argument("--weekly-features", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    protocol = load_protocol()
    panel = attach_features(pd.read_csv(args.paths), pd.read_csv(args.weekly_features))
    table = compare_discovery(panel, protocol)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.output, index=False)
    report = summarize(table, panel, protocol)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
