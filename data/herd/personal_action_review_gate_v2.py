"""최신 연구 게이트를 개인 MVP 행동 경계 보고서로 변환한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
REPORT_PATH = ROOT / "data/reports/personal_action_review_gate_v2.json"
VERSION = "HERD_PERSONAL_ACTION_REVIEW_GATE_V2"


class PersonalActionReviewGateError(ValueError):
    pass


def _load(item: dict[str, str]) -> dict[str, Any]:
    path = (ROOT / item["path"]).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise PersonalActionReviewGateError(f"missing input: {item['path']}")
    if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
        raise PersonalActionReviewGateError(f"input changed: {item['path']}")
    return json.loads(path.read_text())


def build_report(output_path: Path = REPORT_PATH) -> dict[str, Any]:
    contract = json.loads(CONTRACT_PATH.read_text())
    if (
        contract.get("gate_version") != VERSION
        or contract.get("status") != "LOCKED_BEFORE_REVIEW_RESULT"
    ):
        raise PersonalActionReviewGateError("personal review gate is not locked")
    evidence, reentry, cycle, prospective, survivorship = [
        _load(item) for item in contract["inputs"]
    ]
    checks = {
        "profit_take_direction": bool(evidence["admitted_families"]),
        "conditional_reentry": reentry["status"] == "REENTRY_READY_FOR_CYCLE",
        "completed_cycle": cycle["status"] == "READY_FOR_COMPLETED_CYCLE",
        "prospective_shadow": prospective["action_candidate_shadow"] is True,
        "survivorship_safe":
            survivorship["decision"]["survivorship_safe"] is True,
    }
    action_ready = all(checks.values())
    if action_ready:
        raise PersonalActionReviewGateError(
            "human approval artifact is required before action activation"
        )
    report = {
        "report_version": VERSION,
        "status": "STATE_OBSERVATION_MVP_READY",
        "decision": "NO_ADOPTABLE_ACTION_CANDIDATE",
        "model_family": "HERD_STATE_S1",
        "lifecycle": "PERSONAL_RESEARCH_MVP",
        "state_observation_ready": True,
        "transition_observation_ready": True,
        "action_candidate_ready": False,
        "action_model_status": "INDEPENDENT_DIRECTION_EVIDENCE_REJECTED",
        "allowed_scope": [
            "HERD_STATE_S1",
            "HERD_TRANSITION_S1",
            "HISTORICAL_DESCRIPTIVE_CONTEXT",
            "SOURCE_DATE_AND_LIMITATION_DISCLOSURE",
            "PERSONAL_OBSERVATION_LOG",
        ],
        "blocked_scope": [
            "BUY_RATIO",
            "PROFIT_TAKE_RATIO",
            "REENTRY_RATIO",
            "AUTOMATED_ORDER",
            "PUBLIC_INVESTMENT_RECOMMENDATION",
        ],
        "default_action": "HOLD",
        "operational_action_ratio": 0.0,
        "user_action_suppressed": True,
        "herd_state_role": "HERD_STATE_S1_OBSERVATION",
        "historical_role": "CURRENT_CONSTITUENTS_DESCRIPTIVE_ONLY",
        "survivorship_safe": False,
        "blind_holdout_access": False,
        "prospective_shadow_status": "STATE_ONLY_ACTION_SHADOW_BLOCKED",
        "promotion_checks": checks,
        "promotion_blockers": [
            name.upper() + "_NOT_PASSED"
            for name, passed in checks.items()
            if not passed
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(build_report(), indent=2))
