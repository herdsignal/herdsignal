"""State, Action Edge, Portfolio Policy 3-layer contract validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
REPORT_PATH = ROOT / "data/reports/decision_architecture_v1.json"
CONTRACT_VERSION = "HERD_DECISION_ARCHITECTURE_V1"


class DecisionArchitectureError(ValueError):
    """Raised when the action boundary or research target is weakened."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _require_exact_set(actual: list[str], expected: set[str], label: str) -> None:
    if set(actual) != expected or len(actual) != len(expected):
        raise DecisionArchitectureError(f"{label} contract changed")


def validate_contract(contract: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    if (
        contract.get("contract_version") != CONTRACT_VERSION
        or contract.get("status") != "LOCKED_BEFORE_ACTION_EDGE_RESEARCH"
    ):
        raise DecisionArchitectureError("architecture contract is not locked")

    mission = contract.get("mission", {})
    if (
        mission.get("objective")
        != "IMPROVE_TERMINAL_WEALTH_OR_SHARE_COUNT_VERSUS_MATCHED_BUY_AND_HOLD"
        or mission.get("default_action") != "HOLD"
        or mission.get("initial_action_fraction") != 0.05
        or mission.get("full_exit_forbidden") is not True
        or mission.get("leverage_forbidden") is not True
    ):
        raise DecisionArchitectureError("mission or action cap changed")

    input_hashes: list[dict[str, str]] = []
    for item in contract.get("inputs", []):
        path = (root / item["path"]).resolve()
        if root.resolve() not in path.parents or not path.is_file():
            raise DecisionArchitectureError(f"missing architecture input: {item['path']}")
        actual = _sha256(path)
        if actual != item.get("sha256"):
            raise DecisionArchitectureError(f"architecture input hash changed: {item['path']}")
        input_hashes.append({"path": item["path"], "sha256": actual})
    if len(input_hashes) != 5:
        raise DecisionArchitectureError("architecture evidence set is incomplete")

    layers = contract.get("layers", {})
    state = layers.get("state", {})
    action = layers.get("action_edge", {})
    portfolio = layers.get("portfolio_policy", {})
    if (
        state.get("operational_status") != "OBSERVATION_READY"
        or action.get("model") is not None
        or action.get("operational_status") != "NO_ADOPTABLE_CANDIDATE"
        or action.get("primary_target")
        != "NET_TERMINAL_WEALTH_DELTA_VERSUS_MATCHED_HOLD"
        or action.get("oracle_reentry_for_execution") is not False
        or action.get("generic_path_label_as_primary_target") is not False
        or action.get("high_herd_as_action") is not False
        or portfolio.get("model") is not None
        or portfolio.get("operational_status")
        != "BLOCKED_UNTIL_ACTION_EDGE_ADMISSION"
        or portfolio.get("may_change_herd_state") is not False
        or portfolio.get("maximum_initial_fraction") != 0.05
    ):
        raise DecisionArchitectureError("three-layer boundary weakened")

    design = contract.get("research_design", {})
    if (
        design.get("fixed_policy_before_outcomes") is not True
        or design.get("ticker_and_time_blocked_oos") is not True
        or design.get("minimum_oos_years", 0) < 5
        or design.get("maximum_candidates_per_ticker_year", 99) > 2
        or design.get("maximum_feature_families_per_hypothesis", 99) > 3
        or design.get("incremental_group_ablation_required") is not True
        or design.get("same_oos_retuning_forbidden") is not True
    ):
        raise DecisionArchitectureError("research design weakened")

    evaluation = contract.get("evaluation", {})
    if (
        evaluation.get("log_loss_is_sole_admission_gate") is not False
        or evaluation.get("buy_and_hold_is_primary_benchmark") is not True
    ):
        raise DecisionArchitectureError("economic evaluation boundary changed")

    _require_exact_set(
        [track.get("id") for track in contract.get("policy_tracks", [])],
        {"SAME_TICKER_COMPLETED_CYCLE", "RELATIVE_REBALANCE_REVIEW"},
        "policy track",
    )
    _require_exact_set(
        contract.get("stop", []),
        {
            "RUN_LEGACY_V61_ACTION_CALCULATION_ON_OPERATIONAL_STATE_READ",
            "RETUNE_REJECTED_THRESHOLDS_ON_THE_SAME_OOS",
            "ADD_DATA_PARSER_WITHOUT_A_LOCKED_ECONOMIC_HYPOTHESIS",
            "MAP_HIGH_HERD_DIRECTLY_TO_PROFIT_TAKE",
            "RECOMBINE_REJECTED_FEATURES_WITHOUT_A_NEW_INTERACTION_HYPOTHESIS",
            "OPEN_BLIND_HOLDOUT_BEFORE_PREHOLDOUT_PASS",
            "ENABLE_ANY_USER_ACTION_RATIO_BEFORE_PROMOTION",
        },
        "stop",
    )

    firewall = contract.get("firewall", {})
    if (
        firewall.get("adoptable_action_candidate") is not None
        or firewall.get("operational_action") != "HOLD"
        or firewall.get("operational_action_ratio") != 0.0
        or firewall.get("blind_holdout_access") is not False
        or firewall.get("survivorship_safe") is not False
    ):
        raise DecisionArchitectureError("unverified action was promoted")

    return {
        "report_version": CONTRACT_VERSION,
        "status": "ARCHITECTURE_READY_ACTION_EDGE_NOT_TRAINED",
        "layers": {
            "state": "OBSERVATION_READY",
            "action_edge": "NO_ADOPTABLE_CANDIDATE",
            "portfolio_policy": "BLOCKED_UNTIL_ACTION_EDGE_ADMISSION",
        },
        "policy_tracks": [track["id"] for track in contract["policy_tracks"]],
        "next_stage": "FIXED_POLICY_NET_VALUE_TARGET_V1",
        "input_hashes": input_hashes,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
        "survivorship_safe": False,
    }


def run(
    contract_path: Path = CONTRACT_PATH,
    report_path: Path = REPORT_PATH,
) -> dict[str, Any]:
    report = validate_contract(load_contract(contract_path))
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
