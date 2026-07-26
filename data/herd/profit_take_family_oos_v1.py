"""State S1 증거 가족을 하나씩 expanding-fold OOS로 검증한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from herd.simple_action_baselines_v1 import _metrics


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
LABEL_PATH = ROOT / "data/reports/profit_take_success_label_v2.csv"
OUTPUT_PATH = ROOT / "data/reports/profit_take_family_oos_v1.csv"
REPORT_PATH = ROOT / "data/reports/profit_take_family_oos_v1.json"
VERSION = "HERD_PROFIT_TAKE_FAMILY_OOS_V1"
PANEL_PATHS = {
    "PRIMARY": ROOT / "data/walk_forward/herd-state-s1/primary.csv.gz",
    "INDEPENDENT_CURRENT_CONSTITUENTS": ROOT
    / "data/walk_forward/herd-state-s1/independent_current_constituents.csv.gz",
}


class ProfitTakeFamilyOosError(ValueError):
    """단독 가족 검증의 고정 입력·시간·권한 경계가 깨진 경우."""


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_contract(contract: dict[str, Any]) -> dict[str, Any]:
    if (
        contract.get("contract_version") != VERSION
        or contract.get("status") != "LOCKED_BEFORE_FAMILY_RESULTS"
    ):
        raise ProfitTakeFamilyOosError("family OOS contract is not locked")
    for item in contract["inputs"]:
        path = (ROOT / item["path"]).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ProfitTakeFamilyOosError(f"missing input: {item['path']}")
        if _hash(path) != item["sha256"]:
            raise ProfitTakeFamilyOosError(f"input changed: {item['path']}")
    boundary = contract["research_boundary"]
    if (
        boundary["same_sample_threshold_search"] is not False
        or boundary["family_combination_allowed"] is not False
        or boundary["family_weight_learning_allowed"] is not False
        or boundary["survivorship_safe"] is not False
        or boundary["blind_holdout_access"] is not False
        or boundary["operational_action_ratio"] != 0.0
    ):
        raise ProfitTakeFamilyOosError("research boundary weakened")
    return contract


def _fit_logistic(feature: np.ndarray, actual: np.ndarray, penalty: float) -> np.ndarray:
    design = np.column_stack([np.ones(len(feature)), feature])
    beta = np.array([np.log(actual.mean() / (1 - actual.mean())), 0.0])
    for _ in range(50):
        probability = 1 / (1 + np.exp(-np.clip(design @ beta, -30, 30)))
        weights = np.maximum(probability * (1 - probability), 1e-8)
        gradient = design.T @ (probability - actual)
        gradient[1] += penalty * beta[1]
        hessian = design.T @ (weights[:, None] * design)
        hessian[1, 1] += penalty
        step = np.linalg.solve(hessian, gradient)
        beta -= step
        if np.max(np.abs(step)) < 1e-8:
            break
    return beta


def _predict(design_feature: np.ndarray, beta: np.ndarray) -> np.ndarray:
    linear = beta[0] + beta[1] * design_feature
    return np.clip(1 / (1 + np.exp(-np.clip(linear, -30, 30))), 0.001, 0.999)


def _load_population(universe: str) -> pd.DataFrame:
    labels = pd.read_csv(LABEL_PATH, parse_dates=["signal_date"])
    labels = labels[
        labels["success_label"].isin(
            ["ECONOMIC_REBUY_OPPORTUNITY", "HEALTHY_CONTINUATION"]
        )
        & labels["universe_role"].eq(universe)
    ].copy()
    state = pd.read_csv(PANEL_PATHS[universe], parse_dates=["signal_date"])
    state = state.drop(columns=["universe_role"])
    frame = labels.merge(
        state,
        on=["ticker", "signal_date"],
        how="left",
        validate="one_to_one",
    )
    if frame["HERD_STATE"].isna().any():
        raise ProfitTakeFamilyOosError(f"unmatched S1 events in {universe}")
    frame["actual"] = frame["success_label"].eq(
        "ECONOMIC_REBUY_OPPORTUNITY"
    ).astype(int)
    return frame.sort_values(["fold_id", "signal_date", "ticker"]).reset_index(drop=True)


def _evaluate_family(
    frame: pd.DataFrame, family: str, penalty: float
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    records: list[dict[str, Any]] = []
    all_actual: list[int] = []
    all_candidate: list[float] = []
    all_baseline: list[float] = []
    prior = pd.DataFrame()
    for fold in sorted(frame["fold_id"].unique()):
        test = frame[frame["fold_id"].eq(fold)]
        actual = test["actual"].to_numpy()
        if prior.empty:
            baseline_probability = 0.5
            candidate_probability = np.full(len(test), baseline_probability)
        else:
            baseline_probability = float(prior["actual"].mean())
            train_feature = prior[family].astype(float)
            train_median = (
                float(train_feature.median())
                if train_feature.notna().any()
                else 50.0
            )
            beta = _fit_logistic(
                train_feature.fillna(train_median).to_numpy(dtype=float) / 100,
                prior["actual"].to_numpy(dtype=float),
                penalty,
            )
            candidate_probability = _predict(
                test[family]
                .astype(float)
                .fillna(train_median)
                .to_numpy(dtype=float)
                / 100,
                beta,
            )
        baseline = np.full(len(test), np.clip(baseline_probability, 0.001, 0.999))
        candidate_metrics = _metrics(actual, candidate_probability)
        baseline_metrics = _metrics(actual, baseline)
        records.append(
            {
                "fold_id": fold,
                "family": family,
                "rows": len(test),
                **{f"candidate_{key}": value for key, value in candidate_metrics.items()},
                **{f"baseline_{key}": value for key, value in baseline_metrics.items()},
            }
        )
        all_actual.extend(actual.tolist())
        all_candidate.extend(candidate_probability.tolist())
        all_baseline.extend(baseline.tolist())
        prior = pd.concat([prior, test], ignore_index=True)
    candidate = _metrics(np.asarray(all_actual), np.asarray(all_candidate))
    baseline = _metrics(np.asarray(all_actual), np.asarray(all_baseline))
    return records, {
        **{f"candidate_{key}": value for key, value in candidate.items()},
        **{f"baseline_{key}": value for key, value in baseline.items()},
    }


def build_evaluation(
    output_path: Path = OUTPUT_PATH, report_path: Path = REPORT_PATH
) -> dict[str, Any]:
    contract = validate_contract(json.loads(CONTRACT_PATH.read_text()))
    gate = contract["admission_gate"]
    details: list[dict[str, Any]] = []
    summary: dict[str, dict[str, Any]] = {}
    for universe in PANEL_PATHS:
        frame = _load_population(universe)
        summary[universe] = {}
        for family in contract["families_tested_independently"]:
            rows, metrics = _evaluate_family(
                frame, family, contract["estimator"]["slope_l2_penalty"]
            )
            for row in rows:
                row["universe_role"] = universe
            details.extend(rows)
            directional_folds = sum(
                row["candidate_log_loss"] < row["baseline_log_loss"]
                for row in rows
            )
            passed = (
                metrics["baseline_log_loss"] - metrics["candidate_log_loss"]
                >= gate["minimum_log_loss_improvement"]
                and metrics["baseline_brier"] - metrics["candidate_brier"]
                >= gate["minimum_brier_improvement"]
                and metrics["candidate_balanced_accuracy"]
                - metrics["baseline_balanced_accuracy"]
                >= gate["minimum_balanced_accuracy_improvement"]
                and directional_folds >= gate["minimum_directional_folds"]
                and metrics["candidate_action_rate"] <= gate["maximum_action_rate"]
            )
            summary[universe][family] = {
                **metrics,
                "directional_folds": directional_folds,
                "missing_events_imputed": int(frame[family].isna().sum()),
                "events_dropped_for_missing_feature": 0,
                "passed": passed,
            }
    admitted = [
        family
        for family in contract["families_tested_independently"]
        if all(summary[universe][family]["passed"] for universe in PANEL_PATHS)
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(details).to_csv(output_path, index=False)
    report = {
        "report_version": VERSION,
        "status": (
            "FAMILY_EVIDENCE_ADMITTED"
            if admitted
            else "NO_INDEPENDENT_FAMILY_EVIDENCE_ADMITTED"
        ),
        "universe_results": summary,
        "admitted_families": admitted,
        "admitted_count": len(admitted),
        "combination_allowed": bool(admitted),
        "direction_evidence_admitted": bool(admitted),
        "completed_cycle_allowed": False,
        "survivorship_safe": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
        "detail_path": (
            str(output_path.relative_to(ROOT))
            if output_path.is_relative_to(ROOT)
            else str(output_path)
        ),
        "detail_sha256": _hash(output_path),
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(build_evaluation(), indent=2))
