"""동일 Rush 사건에서 실패 가격 가설의 정보 중복만 정량 감사한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_suffix(".json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_protocol(path: Path = PROTOCOL) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_REDUNDANCY_RESULTS":
        raise ValueError("redundancy protocol must be locked before results")
    forbidden = set(protocol.get("forbidden", []))
    if {"LEARN_WEIGHTS", "COMBINE_REJECTED_FEATURES"} - forbidden:
        raise ValueError("rejected features must not be combined or weighted")
    return protocol


def _resolve(path: str) -> Path:
    resolved = (ROOT / path).resolve()
    if not resolved.is_relative_to(ROOT) or not resolved.is_file():
        raise ValueError(f"missing or unsafe source: {path}")
    return resolved


def _standardize(frame: pd.DataFrame) -> np.ndarray:
    filled = frame.fillna(frame.median())
    values = filled.to_numpy(dtype=float)
    scale = values.std(axis=0, ddof=0)
    if np.any(scale == 0):
        raise ValueError("constant feature cannot enter redundancy audit")
    return (values - values.mean(axis=0)) / scale


def _vif(values: np.ndarray, columns: list[str]) -> dict[str, float]:
    result = {}
    for index, column in enumerate(columns):
        target = values[:, index]
        predictors = np.delete(values, index, axis=1)
        design = np.column_stack([np.ones(len(predictors)), predictors])
        fitted, *_ = np.linalg.lstsq(design, target, rcond=None)
        residual = target - design @ fitted
        r_squared = 1.0 - float(residual @ residual) / float(target @ target)
        result[column] = float("inf") if r_squared >= 1.0 else 1.0 / (1.0 - r_squared)
    return result


def _pca(values: np.ndarray, target: float) -> dict:
    _, singular, _ = np.linalg.svd(values, full_matrices=False)
    variance = np.square(singular)
    ratios = variance / variance.sum()
    cumulative = np.cumsum(ratios)
    components = int(np.searchsorted(cumulative, target, side="left") + 1)
    return {
        "explained_variance_ratio": ratios.tolist(),
        "components_for_target": components,
        "target": target,
    }


def _pair_rows(frame: pd.DataFrame, columns: list[str], protocol: dict) -> list[dict]:
    methods = protocol["methods"]
    minimum = int(methods["minimum_complete_pairs"])
    fold_field = protocol["comparable_panel"]["fold_field"]
    rows = []
    for left_index, left in enumerate(columns):
        for right in columns[left_index + 1:]:
            pair = frame[[left, right]].dropna()
            overall = float(pair[left].corr(pair[right], method="spearman")) if len(pair) >= minimum else None
            folds = []
            for fold, group in frame.groupby(fold_field, dropna=False):
                complete = group[[left, right]].dropna()
                rho = (
                    float(complete[left].corr(complete[right], method="spearman"))
                    if len(complete) >= minimum else None
                )
                folds.append({"fold_id": str(fold), "complete_pairs": len(complete), "rho": rho})
            consistent = int(sum(
                item["rho"] is not None
                and overall is not None
                and np.sign(item["rho"]) == np.sign(overall)
                and abs(item["rho"]) >= methods["redundant_pair_absolute_rho"]
                for item in folds
            ))
            rows.append({
                "left": left,
                "right": right,
                "complete_pairs": len(pair),
                "spearman_rho": overall,
                "absolute_rho": abs(overall) if overall is not None else None,
                "folds": folds,
                "redundant_overall": overall is not None
                and abs(overall) >= methods["redundant_pair_absolute_rho"],
                "near_duplicate": overall is not None
                and abs(overall) >= methods["near_duplicate_absolute_rho"],
                "redundant_consistent_folds": consistent,
                "stable_redundant_pair": overall is not None
                and abs(overall) >= methods["redundant_pair_absolute_rho"]
                and consistent >= methods["fold_consistency_minimum_folds"],
            })
    return rows


def audit(protocol_path: Path = PROTOCOL) -> dict:
    protocol = load_protocol(protocol_path)
    panel_path = _resolve(protocol["comparable_panel"]["path"])
    frame = pd.read_csv(panel_path)
    features = protocol["comparable_panel"]["features"]
    columns = [item["column"] for item in features]
    required = set(columns) | set(protocol["comparable_panel"]["event_key"]) | {
        protocol["comparable_panel"]["fold_field"]
    }
    missing = required - set(frame)
    if missing:
        raise ValueError(f"comparable panel missing columns: {sorted(missing)}")
    duplicate_events = int(frame.duplicated(protocol["comparable_panel"]["event_key"]).sum())
    if duplicate_events:
        raise ValueError("comparable panel contains duplicate event keys")
    values = _standardize(frame[columns])
    pairs = _pair_rows(frame, columns, protocol)
    vif = _vif(values, columns)
    pca = _pca(values, float(protocol["methods"]["pca_variance_target"]))
    stable_pairs = [row for row in pairs if row["stable_redundant_pair"]]
    high_vif = {
        column: value for column, value in vif.items()
        if value >= protocol["methods"]["vif_threshold"]
    }
    non_comparable = []
    for family in protocol["non_comparable_families"]:
        path = _resolve(family["path"])
        candidate = pd.read_csv(path)
        non_comparable.append({
            **family,
            "rows": len(candidate),
            "tickers": int(candidate["ticker"].nunique()) if "ticker" in candidate else None,
            "sha256": _sha256(path),
            "quantitative_cross_panel_correlation_executed": False,
        })
    family_redundant = bool(stable_pairs or high_vif)
    return {
        "report_version": "HERD_FAILED_PRICE_INFORMATION_AUDIT_V1",
        "status": "FAILED_PRICE_INFORMATION_REDUNDANCY_MEASURED",
        "protocol_sha256": _sha256(protocol_path),
        "panel_sha256": _sha256(panel_path),
        "events": len(frame),
        "tickers": int(frame["ticker"].nunique()),
        "folds": int(frame[protocol["comparable_panel"]["fold_field"]].nunique()),
        "features": features,
        "missing_fraction": frame[columns].isna().mean().to_dict(),
        "pairwise": pairs,
        "stable_redundant_pairs": [
            {"left": row["left"], "right": row["right"], "rho": row["spearman_rho"]}
            for row in stable_pairs
        ],
        "near_duplicate_pairs": [
            {"left": row["left"], "right": row["right"], "rho": row["spearman_rho"]}
            for row in pairs if row["near_duplicate"]
        ],
        "vif": vif,
        "high_vif_features": high_vif,
        "pca": pca,
        "family_redundant": family_redundant,
        "family_compressed": pca["components_for_target"] < len(columns),
        "non_comparable_families": non_comparable,
        "outcome_used_for_selection": False,
        "feature_admission_count": 0,
        "weights_allowed": False,
        "herd_formula_change_allowed": False,
        "operational_action_authority": False,
        "blind_holdout_access": False,
        "next_decision": "AUDIT_MISSING_NON_PRICE_INFORMATION_DOMAINS",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.protocol)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
