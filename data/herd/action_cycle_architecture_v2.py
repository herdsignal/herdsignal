"""행동 모델의 제품·연구·현금 사이클 경계를 하나의 fail-closed 계약으로 감사한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
REPORT_PATH = ROOT / "data/reports/action_cycle_architecture_v2.json"
VERSION = "HERD_ACTION_CYCLE_ARCHITECTURE_V2"


class ActionCycleArchitectureError(ValueError):
    """계약 해시나 행동 권한 경계가 달라졌을 때 발생한다."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(relative: str) -> dict[str, Any]:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ActionCycleArchitectureError(f"missing input: {relative}")
    return json.loads(path.read_text())


def validate_contract(contract: dict[str, Any]) -> dict[str, Any]:
    if (
        contract.get("contractVersion") != VERSION
        or contract.get("status") != "LOCKED_BEFORE_NEW_DIRECTION_RESULTS"
    ):
        raise ActionCycleArchitectureError("action architecture is not locked")

    for item in contract.get("pinnedInputs", []):
        path = (ROOT / item["path"]).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ActionCycleArchitectureError(f"missing input: {item['path']}")
        if _sha256(path) != item["sha256"]:
            raise ActionCycleArchitectureError(f"input changed: {item['path']}")

    lanes = contract.get("actionLanes", {})
    state_machine = contract.get("cycleStateMachine", {})
    policy = contract.get("riskPolicy", {})
    boundary = contract.get("currentBoundary", {})
    product_lanes = {item["id"]: item for item in contract.get("productLanes", [])}
    required_completion_rules = {
        "EXPLICIT_CYCLE_ID",
        "SAME_TICKER",
        "REENTRY_AFTER_TRIM",
        "REENTRY_COST_NOT_ABOVE_MATCHED_NET_SALE_CASH",
        "NO_EXTERNAL_CASH",
        "NO_UNMATCHED_BUY",
    }
    if (
        set(lanes) != {"profitTake", "matchedCashReentry", "newEntry"}
        or lanes["matchedCashReentry"].get("requiresPriorSaleCash") is not True
        or lanes["matchedCashReentry"].get("unknownBusinessGatePolicy") != "BLOCK"
        or lanes["newEntry"].get("mayReuseReentryRule") is not False
        or state_machine.get("expiredCycleCountsAsSuccess") is not False
        or not required_completion_rules.issubset(
            state_machine.get("completedRequires", [])
        )
        or policy.get("initialTrimFraction") != 0.05
        or policy.get("maximumCumulativeTrimFraction") != 0.15
        or policy.get("maximumReentryWaitSessions") != 126
        or policy.get("fullExitAllowed") is not False
        or policy.get("leverageAllowed") is not False
        or boundary.get("level") != "OBSERVATION"
        or boundary.get("operationalAction") != "HOLD"
        or boundary.get("operationalActionRatio") != 0.0
        or boundary.get("blindHoldoutAccess") is not False
        or product_lanes.get("OBSERVATION_AND_POLICY_REVIEW", {}).get(
            "mayAuthorizeTrade"
        )
        is not False
        or product_lanes.get("PREDICTIVE_ACTION_CYCLE", {}).get(
            "availableBeforeDirectionEvidence"
        )
        is not False
    ):
        raise ActionCycleArchitectureError("action boundary was weakened")
    return contract


def build_report(
    report_path: Path = REPORT_PATH,
    *,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = validate_contract(
        contract or json.loads(CONTRACT_PATH.read_text())
    )
    ceiling = _load_json("data/reports/profit_take_opportunity_ceiling_v1.json")
    labels = _load_json("data/reports/profit_take_success_label_v2.json")
    target_gate = _load_json("data/reports/profit_take_contract_gate_v1.json")
    failed = _load_json("data/herd/failed_hypothesis_map_v1.json")
    boundary = contract["currentBoundary"]

    checks = {
        "opportunity_ceiling": ceiling.get("status")
        == boundary["opportunityCeilingRequiredStatus"]
        and ceiling.get("passed") is True,
        "label_coverage": labels.get("status")
        == boundary["labelCoverageRequiredStatus"]
        and labels.get("coverage_passed") is True,
        "target_and_frequency_locked": target_gate.get("status")
        == boundary["contractGateRequiredStatus"],
        "all_recorded_hypotheses_rejected": failed.get("audit_summary", {}).get(
            "adoptable_direction_count"
        )
        == 0,
        "profit_take_direction_not_admitted": boundary[
            "admittedProfitTakeDirectionEvidence"
        ]
        == 0,
        "reentry_direction_not_admitted": boundary[
            "admittedReentryDirectionEvidence"
        ]
        == 0,
        "operational_action_fail_closed": boundary["operationalAction"] == "HOLD"
        and boundary["operationalActionRatio"] == 0.0,
    }
    foundation_ready = all(
        checks[key]
        for key in (
            "opportunity_ceiling",
            "label_coverage",
            "target_and_frequency_locked",
        )
    )
    direction_ready = not checks["profit_take_direction_not_admitted"]
    reentry_ready = direction_ready and not checks["reentry_direction_not_admitted"]
    report = {
        "reportVersion": VERSION,
        "status": "ACTION_FOUNDATION_READY_DIRECTION_BLOCKED"
        if foundation_ready
        else "ACTION_FOUNDATION_INVALID",
        "checks": checks,
        "foundationReady": foundation_ready,
        "currentProductLevel": "OBSERVATION",
        "directionTargetDefined": foundation_ready,
        "newCandidateReady": False,
        "directionResearchReady": False,
        "profitTakeReviewAllowed": direction_ready,
        "matchedCashReentryReviewAllowed": reentry_ready,
        "shadowCycleAllowed": False,
        "operationalActionAllowed": False,
        "operationalAction": "HOLD",
        "operationalActionRatio": 0.0,
        "nextGate": contract["nextGate"]["id"],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(build_report(), indent=2))
