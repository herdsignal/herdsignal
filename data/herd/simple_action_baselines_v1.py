"""State S1 익절 연구의 단순 사건 기준선을 고정 평가한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
LABEL_PATH = ROOT / "data/reports/profit_take_success_label_v2.csv"
OUTPUT_PATH = ROOT / "data/reports/simple_action_baselines_v1.csv"
REPORT_PATH = ROOT / "data/reports/simple_action_baselines_v1.json"
VERSION = "HERD_SIMPLE_ACTION_BASELINES_V1"
PRIMARY_LABELS = {"ECONOMIC_REBUY_OPPORTUNITY", "HEALTHY_CONTINUATION"}


class SimpleActionBaselineError(ValueError):
    """기준선의 시간·표본·운영 경계가 깨진 경우."""


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _display_path(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def validate_contract(contract: dict[str, Any]) -> dict[str, Any]:
    if (
        contract.get("contract_version") != VERSION
        or contract.get("status") != "LOCKED_BEFORE_BASELINE_RESULTS"
    ):
        raise SimpleActionBaselineError("baseline contract is not locked")
    for item in contract["inputs"]:
        path = (ROOT / item["path"]).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise SimpleActionBaselineError(f"missing input: {item['path']}")
        if _hash(path) != item["sha256"]:
            raise SimpleActionBaselineError(f"input changed: {item['path']}")
    firewall = contract["firewall"]
    if (
        firewall["herd_predictor_training_allowed"] is not False
        or firewall["baseline_pass_authorizes_action"] is not False
        or firewall["survivorship_safe"] is not False
        or firewall["blind_holdout_access"] is not False
        or firewall["operational_action_ratio"] != 0.0
    ):
        raise SimpleActionBaselineError("baseline firewall weakened")
    return contract


def _metrics(actual: np.ndarray, probability: np.ndarray) -> dict[str, float]:
    probability = np.clip(probability.astype(float), 0.001, 0.999)
    predicted = probability >= 0.5
    positive = actual == 1
    negative = ~positive
    sensitivity = float(predicted[positive].mean()) if positive.any() else 0.0
    specificity = float((~predicted[negative]).mean()) if negative.any() else 0.0
    return {
        "brier": float(np.mean((probability - actual) ** 2)),
        "log_loss": float(
            -np.mean(
                actual * np.log(probability)
                + (1 - actual) * np.log(1 - probability)
            )
        ),
        "balanced_accuracy": (sensitivity + specificity) / 2,
        "action_rate": float(predicted.mean()),
    }


def _expanding_prior_prevalence(frame: pd.DataFrame, contract: dict) -> np.ndarray:
    baseline = next(
        item
        for item in contract["event_level_baselines"]
        if item["id"] == "EXPANDING_PRIOR_PREVALENCE"
    )
    result = np.full(len(frame), baseline["cold_start_probability"], dtype=float)
    ordered_folds = sorted(frame["fold_id"].unique())
    prior_actual: list[int] = []
    for fold in ordered_folds:
        mask = frame["fold_id"].eq(fold).to_numpy()
        if prior_actual:
            probability = float(np.mean(prior_actual))
            result[mask] = np.clip(
                probability,
                baseline["minimum_probability"],
                baseline["maximum_probability"],
            )
        prior_actual.extend(frame.loc[mask, "actual"].astype(int).tolist())
    return result


def _probabilities(frame: pd.DataFrame, contract: dict) -> dict[str, np.ndarray]:
    policies = {
        item["id"]: item for item in contract["event_level_baselines"]
    }
    ordinal = frame["ticker_year_ordinal"].astype(int).to_numpy()
    first = policies["FIRST_RUSH_PER_TICKER_YEAR"]
    return {
        "NEVER_TRIM": np.full(len(frame), policies["NEVER_TRIM"]["probability"]),
        "ALWAYS_TRIM": np.full(len(frame), policies["ALWAYS_TRIM"]["probability"]),
        "FIRST_RUSH_PER_TICKER_YEAR": np.where(
            ordinal == 1,
            first["probability_if_first"],
            first["probability_otherwise"],
        ),
        "EXPANDING_PRIOR_PREVALENCE": _expanding_prior_prevalence(
            frame, contract
        ),
    }


def build_baselines(
    output_path: Path = OUTPUT_PATH, report_path: Path = REPORT_PATH
) -> dict[str, Any]:
    contract = validate_contract(json.loads(CONTRACT_PATH.read_text()))
    source = pd.read_csv(LABEL_PATH, parse_dates=["signal_date"])
    frame = source[source["success_label"].isin(PRIMARY_LABELS)].copy()
    frame["actual"] = frame["success_label"].eq(
        "ECONOMIC_REBUY_OPPORTUNITY"
    ).astype(int)
    frame["ticker_year_ordinal"] = (
        frame.sort_values("signal_date")
        .groupby(["ticker", frame["signal_date"].dt.year])
        .cumcount()
        .add(1)
    )
    if frame.empty or frame.duplicated(["ticker", "signal_date"]).any():
        raise SimpleActionBaselineError("baseline population is empty or duplicated")

    detail: list[dict[str, Any]] = []
    aggregate: dict[str, dict[str, dict[str, float]]] = {}
    for universe, lane in frame.groupby("universe_role", sort=False):
        aggregate[universe] = {}
        probabilities = _probabilities(lane, contract)
        actual = lane["actual"].to_numpy()
        for policy, probability in probabilities.items():
            aggregate[universe][policy] = {
                "rows": int(len(lane)),
                **_metrics(actual, probability),
            }
            for fold in sorted(lane["fold_id"].unique()):
                mask = lane["fold_id"].eq(fold).to_numpy()
                detail.append(
                    {
                        "universe_role": universe,
                        "fold_id": fold,
                        "policy": policy,
                        "rows": int(mask.sum()),
                        **_metrics(actual[mask], probability[mask]),
                    }
                )

    selected_floors = {
        universe: min(
            policies,
            key=lambda policy: policies[policy]["log_loss"],
        )
        for universe, policies in aggregate.items()
    }
    checks = {}
    reporting = contract["reporting"]
    for universe, lane in frame.groupby("universe_role", sort=False):
        checks[f"{universe}_minimum_rows"] = (
            len(lane) >= reporting["minimum_rows_each_universe"]
        )
        checks[f"{universe}_minimum_folds"] = (
            lane["fold_id"].nunique()
            >= reporting["minimum_folds_each_universe"]
        )

    result = pd.DataFrame(detail)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    report = {
        "report_version": VERSION,
        "status": (
            "SIMPLE_BASELINE_FLOORS_ESTABLISHED"
            if all(checks.values())
            else "SIMPLE_BASELINE_COVERAGE_FAILED"
        ),
        "scored_rows": int(len(frame)),
        "excluded_label_counts": {
            label: int((source["success_label"] == label).sum())
            for label in ("STRUCTURAL_DAMAGE", "NO_ECONOMIC_EDGE")
        },
        "universe_aggregate": aggregate,
        "selected_floor_by_universe": selected_floors,
        "checks": checks,
        "coverage_passed": all(checks.values()),
        "candidate_gate": contract["candidate_gate_for_next_stage"],
        "deferred_non_commensurable_baselines": contract[
            "deferred_non_commensurable_baselines"
        ],
        "direction_evidence_admitted": False,
        "herd_predictor_trained": False,
        "baseline_results_authorize_action": False,
        "survivorship_safe": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
        "detail_path": _display_path(output_path),
        "detail_sha256": _hash(output_path),
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(build_baselines(), indent=2))
