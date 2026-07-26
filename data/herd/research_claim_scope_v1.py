"""현재 데이터가 허용하는 연구·제품 주장의 범위를 검증한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
REPORT_PATH = ROOT / "data/reports/research_claim_scope_v1.json"
VERSION = "HERD_RESEARCH_CLAIM_SCOPE_V1"


class ResearchClaimScopeError(ValueError):
    """현재 근거보다 넓은 주장이나 행동 권한이 감지된 경우."""


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_scope(contract: dict[str, Any]) -> dict[str, Any]:
    if (
        contract.get("contract_version") != VERSION
        or contract.get("status") != "LOCKED_BEFORE_BASELINE_RESULTS"
    ):
        raise ResearchClaimScopeError("claim scope is not locked")
    loaded: dict[str, dict[str, Any]] = {}
    for item in contract["inputs"]:
        path = (ROOT / item["path"]).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ResearchClaimScopeError(f"missing input: {item['path']}")
        if _hash(path) != item["sha256"]:
            raise ResearchClaimScopeError(f"input changed: {item['path']}")
        if path.suffix == ".json":
            loaded[item["path"]] = json.loads(path.read_text())

    lanes = contract["lanes"]
    personal = lanes["PERSONAL_PROSPECTIVE_SHADOW"]
    market = lanes["MARKET_GENERAL_ACTION_MODEL"]
    gate = contract["shared_operational_gate"]
    survivorship = loaded["data/herd/survivorship_readiness_v2.json"]
    labels = loaded["data/reports/profit_take_success_label_v2.json"]
    if (
        survivorship["decision"]["survivorship_safe"] is not False
        or labels["coverage_passed"] is not True
        or any(lane["may_authorize_user_action"] for lane in lanes.values())
        or personal["interim_outcome_peeking"] is not False
        or personal["may_train_or_retune"] is not False
        or personal["may_auto_authorize_user_action"] is not False
        or market["current_status"] != "BLOCKED"
        or market["may_claim_generalization"] is not False
        or gate["survivorship_safe_required"] is not True
        or gate["blind_holdout_single_evaluation_required"] is not True
        or gate["human_approval_required"] is not True
        or gate["maximum_action_fraction"] != 0.05
        or gate["current_operational_action_ratio"] != 0.0
        or contract["next_stage"]["herd_predictor_training_allowed"] is not False
    ):
        raise ResearchClaimScopeError("claim or action boundary was widened")
    return {
        "report_version": VERSION,
        "status": "CLAIM_LANES_SEPARATED",
        "current_holding_research": "PREHOLDOUT_ALLOWED_WITH_DISCLOSURE",
        "personal_prospective_shadow": "BLOCKED_UNTIL_PREHOLDOUT_CYCLE_PASS",
        "market_general_model": "BLOCKED_SURVIVORSHIP_UNSAFE",
        "next_stage": contract["next_stage"]["id"],
        "operational_action_ratio": 0.0,
    }


def build_report(output_path: Path = REPORT_PATH) -> dict[str, Any]:
    report = validate_scope(json.loads(CONTRACT_PATH.read_text()))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(build_report(), indent=2))
