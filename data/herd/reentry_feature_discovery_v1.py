"""새 재진입 가치 목표에서 기존 네 신호의 발견 효과와 시대 반복성을 감사한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from herd.rush_path_comparison_v2 import _holm, _rank_biserial


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json")


def load_protocol(path: Path = PROTOCOL_PATH) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_REENTRY_TARGET_FEATURE_RESULTS":
        raise ValueError("reentry feature discovery protocol must be locked")
    if protocol["interpretation"].get("retained_means_preregister_for_new_sample_only") is not True:
        raise ValueError("discovery promotion boundary is missing")
    return protocol


def attach_signal_features(targets: pd.DataFrame, panel: pd.DataFrame, protocol: dict) -> pd.DataFrame:
    features = [row["id"] for row in protocol["candidate_features"]]
    required_target = {"ticker", "episode_id", "signal_date", "target_label"}
    required_panel = {"ticker", "episode_id", *features}
    if not required_target.issubset(targets) or not required_panel.issubset(panel):
        raise ValueError("target or signal panel schema mismatch")
    if panel.duplicated(["ticker", "episode_id"]).any():
        raise ValueError("signal panel episode key is not unique")
    return targets.merge(
        panel[["ticker", "episode_id", *features]],
        on=["ticker", "episode_id"],
        how="left",
        validate="one_to_one",
    )


def compare(panel: pd.DataFrame, protocol: dict) -> pd.DataFrame:
    panel = panel.copy()
    panel["signal_date"] = pd.to_datetime(panel["signal_date"])
    treatment_label = protocol["comparison"]["treatment"]
    control_label = protocol["comparison"]["control"]
    rows = []
    for candidate in protocol["candidate_features"]:
        feature = candidate["id"]
        treatment = panel.loc[panel["target_label"].eq(treatment_label), feature].dropna()
        control = panel.loc[panel["target_label"].eq(control_label), feature].dropna()
        effect, p_value = _rank_biserial(treatment, control) if len(treatment) and len(control) else (np.nan, 1.0)
        era_effects = []
        for start, end in protocol["retention_gate"]["eras"]:
            era = panel[panel["signal_date"].between(pd.Timestamp(start), pd.Timestamp(end))]
            left = era.loc[era["target_label"].eq(treatment_label), feature].dropna()
            right = era.loc[era["target_label"].eq(control_label), feature].dropna()
            era_effect = _rank_biserial(left, right)[0] if len(left) >= 30 and len(right) >= 30 else None
            era_effects.append({"start": start, "end": end, "rank_biserial": era_effect})
        same_direction = sum(
            item["rank_biserial"] is not None
            and np.sign(item["rank_biserial"]) == np.sign(effect)
            for item in era_effects
        )
        rows.append({
            "feature": feature,
            "treatment_events": int(len(treatment)),
            "control_events": int(len(control)),
            "missing_fraction": float(panel[feature].isna().mean()),
            "treatment_median": float(treatment.median()) if len(treatment) else None,
            "control_median": float(control.median()) if len(control) else None,
            "rank_biserial": float(effect),
            "raw_p_value": float(p_value),
            "era_effects": era_effects,
            "same_direction_eras": same_direction,
        })
    _holm(rows)
    gate = protocol["retention_gate"]
    for row in rows:
        row["retained_for_new_sample_preregistration"] = bool(
            row["treatment_events"] >= gate["minimum_treatment_events"]
            and row["control_events"] >= gate["minimum_control_events"]
            and row["missing_fraction"] <= gate["maximum_missing_fraction"]
            and abs(row["rank_biserial"]) >= gate["minimum_absolute_rank_biserial"]
            and row["holm_p_value"] <= gate["maximum_holm_p_value"]
            and row["same_direction_eras"] >= gate["minimum_same_direction_eras"]
        )
    return pd.DataFrame(rows)


def run(protocol_path: Path = PROTOCOL_PATH) -> tuple[pd.DataFrame, dict]:
    protocol = load_protocol(protocol_path)
    paths = {name: (ROOT / protocol[name]).resolve() for name in ("target_report", "target_rows", "signal_panel")}
    if any(not path.is_relative_to(ROOT) or not path.is_file() for path in paths.values()):
        raise ValueError("required discovery input missing or outside repository")
    target_report = json.loads(paths["target_report"].read_text(encoding="utf-8"))
    if target_report.get("status") != "DISCOVERY_TARGET_READY":
        raise ValueError("reentry target is not ready")
    panel = attach_signal_features(
        pd.read_csv(paths["target_rows"]),
        pd.read_csv(paths["signal_panel"]),
        protocol,
    )
    comparison = compare(panel, protocol)
    retained = comparison.loc[
        comparison["retained_for_new_sample_preregistration"], "feature"
    ].tolist()
    report = {
        "report_version": "HERD_REENTRY_FEATURE_DISCOVERY_V1",
        "status": "DISCOVERY_COMPLETE",
        "target_events": int(len(panel)),
        "features_compared": int(len(comparison)),
        "retained_features": retained,
        "retained_count": len(retained),
        "independent_oos_passed_features": [],
        "same_sample_confirmation_allowed": False,
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
    }
    return comparison, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    comparison, report = run()
    args.comparison.parent.mkdir(parents=True, exist_ok=True)
    comparison.to_json(args.comparison, orient="records", indent=2)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
