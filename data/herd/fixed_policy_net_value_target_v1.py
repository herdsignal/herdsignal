"""Validate the fixed-policy economic target before any policy result is opened."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
REPORT_PATH = ROOT / "data/reports/fixed_policy_net_value_target_v1.json"
CONTRACT_VERSION = "HERD_FIXED_POLICY_NET_VALUE_TARGET_V1"


class FixedPolicyTargetError(ValueError):
    """Raised when a causal or economic comparison boundary is weakened."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _require_exact(actual: list[str], expected: set[str], label: str) -> None:
    if len(actual) != len(expected) or set(actual) != expected:
        raise FixedPolicyTargetError(f"{label} contract changed")


def validate_contract(contract: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    if (
        contract.get("contract_version") != CONTRACT_VERSION
        or contract.get("status") != "LOCKED_BEFORE_POLICY_BASELINE_RESULTS"
        or contract.get("objective")
        != "MEASURE_INCREMENTAL_ECONOMIC_VALUE_OF_A_PREREGISTERED_FIXED_POLICY_VERSUS_MATCHED_HOLD"
    ):
        raise FixedPolicyTargetError("target contract is not locked")

    checked_inputs: list[dict[str, str]] = []
    for item in contract.get("inputs", []):
        path = (root / item["path"]).resolve()
        if root.resolve() not in path.parents or not path.is_file():
            raise FixedPolicyTargetError(f"missing target input: {item['path']}")
        actual = _sha256(path)
        if actual != item.get("sha256"):
            raise FixedPolicyTargetError(f"target input hash changed: {item['path']}")
        checked_inputs.append({"path": item["path"], "sha256": actual})
    if len(checked_inputs) != 3:
        raise FixedPolicyTargetError("target evidence set is incomplete")

    unit = contract.get("observation_unit", {})
    if (
        unit.get("signal_information_cutoff") != "SESSION_CLOSE"
        or unit.get("execution_earliest") != "NEXT_AVAILABLE_SESSION_OPEN"
        or unit.get("fixed_horizon_sessions") != 126
        or unit.get("minimum_mature_horizon_sessions") != 126
        or unit.get("maximum_events_per_ticker_year", 99) > 2
        or unit.get("right_censored_events")
        != "EXCLUDE_FROM_PRIMARY_TARGET_AND_REPORT_SEPARATELY"
    ):
        raise FixedPolicyTargetError("observation timing or action budget changed")

    benchmark = contract.get("matched_hold_benchmark", {})
    required_match = {
        "same_ticker",
        "same_initial_shares",
        "same_initial_cash",
        "same_start_and_end_sessions",
        "same_external_cashflows",
        "same_split_and_dividend_treatment",
        "same_execution_price_source",
        "policy_costs_applied_only_when_traded",
    }
    if any(benchmark.get(field) is not True for field in required_match):
        raise FixedPolicyTargetError("matched HOLD comparison weakened")

    tracks = contract.get("policy_tracks", {})
    if set(tracks) != {
        "SAME_TICKER_COMPLETED_CYCLE",
        "RELATIVE_REBALANCE_REVIEW",
    }:
        raise FixedPolicyTargetError("policy track contract changed")
    if (
        tracks["SAME_TICKER_COMPLETED_CYCLE"].get("initial_trim_fraction") != 0.05
        or tracks["SAME_TICKER_COMPLETED_CYCLE"].get("reentry_rule") is not None
        or tracks["SAME_TICKER_COMPLETED_CYCLE"].get(
            "incomplete_cycle_counts_as_success"
        )
        is not False
        or tracks["RELATIVE_REBALANCE_REVIEW"].get(
            "initial_reallocation_fraction"
        )
        != 0.05
        or tracks["RELATIVE_REBALANCE_REVIEW"].get("destination_rule") is not None
    ):
        raise FixedPolicyTargetError("unregistered policy rule was introduced")

    target = contract.get("primary_target", {})
    if (
        target.get("name") != "NET_TERMINAL_WEALTH_DELTA_VERSUS_MATCHED_HOLD"
        or target.get("formula")
        != "POLICY_TERMINAL_WEALTH_MINUS_MATCHED_HOLD_TERMINAL_WEALTH"
        or target.get("normalization") != "DIVIDE_BY_EVENT_START_TOTAL_WEALTH"
    ):
        raise FixedPolicyTargetError("primary economic target changed")

    _require_exact(
        contract.get("required_secondary_targets", []),
        {
            "TERMINAL_SHARE_DELTA",
            "MISSED_UPSIDE_COST",
            "DOWNSIDE_AVOIDED",
            "COMPLETED_POLICY",
            "AVERAGE_EQUITY_EXPOSURE",
            "ONE_WAY_TURNOVER",
            "BASE_COST_NET_VALUE",
            "STRESS_COST_NET_VALUE",
        },
        "secondary target",
    )

    registration = contract.get("policy_registration", {})
    if (
        registration.get("required_before_target_generation") is not True
        or registration.get("result_dependent_rule_selection_forbidden") is not True
        or registration.get("oracle_reentry_forbidden") is not True
        or registration.get("current_registered_policy") is not None
    ):
        raise FixedPolicyTargetError("policy preregistration boundary weakened")
    _require_exact(
        registration.get("must_lock", []),
        {
            "ELIGIBILITY_FORMULA",
            "ACTION_DATE",
            "EXECUTION_DATE",
            "EXIT_OR_REALLOCATION_RULE",
            "REENTRY_OR_DESTINATION_RULE",
            "COOLDOWN",
            "ACTION_BUDGET",
            "COST_ASSUMPTIONS",
            "OOS_SPLITS",
        },
        "policy registration field",
    )

    costs = contract.get("cost_contract", {})
    if (
        costs.get("base_one_way_bps") != 10
        or costs.get("stress_one_way_bps") != [25, 50]
        or costs.get("taxes")
        != "REPORT_SEPARATELY_NOT_ASSUMED_ZERO_IN_PRODUCT_TRANSLATION"
    ):
        raise FixedPolicyTargetError("cost contract changed")

    evaluation = contract.get("evaluation", {})
    if (
        evaluation.get("buy_and_hold_is_primary_benchmark") is not True
        or evaluation.get("classification_score_is_not_primary_gate") is not True
        or evaluation.get("uncertainty") != "TICKER_BLOCK_BOOTSTRAP_INTERVAL"
    ):
        raise FixedPolicyTargetError("economic evaluation contract changed")

    _require_exact(
        contract.get("forbidden", []),
        {
            "USE_GENERIC_PATH_LABEL_AS_PRIMARY_TARGET",
            "USE_FUTURE_LOW_AS_EXECUTABLE_REENTRY",
            "COUNT_OPEN_TRIM_AS_COMPLETED_CYCLE",
            "TREAT_ABSTENTION_AS_PROFITABLE_ACTION",
            "SELECT_POLICY_RULE_AFTER_VIEWING_TARGET_RESULTS",
            "ACTIVATE_USER_ACTION_FROM_THIS_TARGET_CONTRACT",
            "OPEN_BLIND_HOLDOUT",
        },
        "forbidden",
    )

    firewall = contract.get("firewall", {})
    if (
        firewall.get("target_generation_allowed") is not False
        or firewall.get("reason") != "NO_FIXED_POLICY_REGISTERED"
        or firewall.get("operational_action") != "HOLD"
        or firewall.get("operational_action_ratio") != 0.0
        or firewall.get("blind_holdout_access") is not False
    ):
        raise FixedPolicyTargetError("target firewall weakened")

    return {
        "report_version": CONTRACT_VERSION,
        "status": "TARGET_LOCKED_POLICY_BASELINES_NOT_BUILT",
        "primary_target": target["name"],
        "policy_tracks": list(tracks),
        "target_generation_allowed": False,
        "blocked_reason": "NO_FIXED_POLICY_REGISTERED",
        "next_stage": "SIMPLE_FIXED_POLICY_BASELINES_V1",
        "input_hashes": checked_inputs,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
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
