"""Rush episode 직전 4주 변화량을 만들고 발견구간 반복성을 비교한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from herd.rush_path_comparison_v2 import _holm, _rank_biserial


CONTRACT_PATH = Path(__file__).with_suffix(".json")
SOURCE_MAP = {
    "SECTOR_RS_DELTA_4W": "STOCK_SECTOR_RS_13W",
    "SECTOR_RS_DAMAGE_DELTA_4W": "STOCK_SECTOR_RS_DAMAGE",
    "SPY_RS_DELTA_4W": "STOCK_SPY_RS_13W",
    "HIGH_FAILURE_DELTA_4W": "HIGH_52W_FAILURE",
    "PARTICIPATION_WEAKENING_DELTA_4W": "SIGNED_VOLUME_PARTICIPATION",
    "MARKET_STRESS_DELTA_4W": "MARKET_STRESS_REGIME",
    "TREND_QUALITY_DELTA_4W": "TREND_26W_QUALITY",
    "DECELERATION_DELTA_4W": "TREND_13W_DECELERATION",
}


def load_contract(path: Path = CONTRACT_PATH) -> dict:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract.get("feature_version") != "HERD_RUSH_TRANSITION_FEATURES_V1" \
            or contract.get("status") != "LOCKED_BEFORE_TRANSITION_RESULTS":
        raise ValueError("Rush transition feature contract is not locked")
    if contract.get("lookback_completed_weeks") != 4:
        raise ValueError("transition lookback changed")
    return contract


def build_transition_panel(paths: pd.DataFrame, weekly: pd.DataFrame, contract: dict) -> pd.DataFrame:
    weekly = weekly.copy()
    paths = paths.copy()
    weekly["signal_date"] = pd.to_datetime(weekly["signal_date"])
    paths["signal_date"] = pd.to_datetime(paths["signal_date"])
    weekly = weekly.sort_values(["ticker", "signal_date"])
    lookback = contract["lookback_completed_weeks"]
    for target, source in SOURCE_MAP.items():
        weekly[target] = weekly.groupby("ticker", sort=False)[source].diff(lookback)
    columns = ["ticker", "signal_date", *SOURCE_MAP]
    return paths.merge(weekly[columns], on=["ticker", "signal_date"], how="left", validate="one_to_one")


def compare_transitions(panel: pd.DataFrame, contract: dict) -> pd.DataFrame:
    rule = contract["comparison"]
    discovery = panel[pd.to_datetime(panel["signal_date"]) <= pd.Timestamp(rule["discovery_end"])]
    eligible = discovery[discovery["path_label"].isin(rule["treatment_labels"] + rule["control_labels"])]
    cut = pd.Timestamp("2013-12-31")
    rows = []
    for feature in SOURCE_MAP:
        treatment = eligible[eligible["path_label"].isin(rule["treatment_labels"])][feature].dropna()
        control = eligible[eligible["path_label"].isin(rule["control_labels"])][feature].dropna()
        effect, p_value = _rank_biserial(treatment, control) if not treatment.empty and not control.empty else (np.nan, 1.0)
        half_effects = []
        for mask in (eligible["signal_date"] <= cut, eligible["signal_date"] > cut):
            half = eligible[mask]
            left = half[half["path_label"].isin(rule["treatment_labels"])][feature].dropna()
            right = half[half["path_label"].isin(rule["control_labels"])][feature].dropna()
            half_effects.append(_rank_biserial(left, right)[0] if len(left) >= 5 and len(right) >= 5 else np.nan)
        rows.append({
            "feature": feature,
            "treatment_events": len(treatment),
            "control_events": len(control),
            "missing_fraction": float(eligible[feature].isna().mean()),
            "treatment_median": float(treatment.median()) if not treatment.empty else None,
            "control_median": float(control.median()) if not control.empty else None,
            "rank_biserial": effect,
            "raw_p_value": p_value,
            "first_half_effect": half_effects[0],
            "second_half_effect": half_effects[1],
            "same_direction_halves": sum(np.isfinite(value) and np.sign(value) == np.sign(effect) for value in half_effects),
        })
    _holm(rows)
    for row in rows:
        row["retained_for_preregistration"] = bool(
            row["treatment_events"] >= rule["minimum_treatment_events"]
            and row["control_events"] >= rule["minimum_control_events"]
            and row["missing_fraction"] <= rule["maximum_missing_fraction"]
            and abs(row["rank_biserial"]) >= rule["minimum_absolute_rank_biserial"]
            and row["holm_p_value"] <= rule["maximum_holm_p_value"]
            and row["same_direction_halves"] >= rule["minimum_same_direction_halves"]
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paths", type=Path, required=True)
    parser.add_argument("--weekly-features", type=Path, required=True)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    contract = load_contract()
    panel = build_transition_panel(pd.read_csv(args.paths), pd.read_csv(args.weekly_features), contract)
    comparison = compare_transitions(panel, contract)
    args.panel.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.panel, index=False)
    comparison.to_csv(args.comparison, index=False)
    retained = comparison.loc[comparison["retained_for_preregistration"], "feature"].tolist()
    report = {
        "report_version":"herd-rush-transition-features-v1",
        "episodes":len(panel), "features_compared":len(comparison),
        "retained_features":retained, "retained_count":len(retained),
        "confirmation_rows_accessed_for_selection":False,
        "operational_action_ratio":0.0, "blind_holdout_access":False
    }
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
