"""현재 HERD 연구 결정을 과거 해시 체인을 깨지 않고 단일 검증한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DECISION_PATH = Path(__file__).with_suffix(".json")
CATALOG_PATH = Path(__file__).with_name("research_artifact_catalog_v2.json")
VERSION = "HERD_RESEARCH_DECISION_V2"


class ResearchDecisionError(ValueError):
    """현재 연구 결정과 고정 근거가 충돌하는 경우."""


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_decision(decision: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    if (
        decision.get("decision_version") != VERSION
        or decision.get("status")
        != "STATE_OBSERVATION_MVP_READY_NO_ACTION_CANDIDATE"
        or decision.get("preserves_v1_as_reproducibility_input") is not True
    ):
        raise ResearchDecisionError("current decision boundary changed")

    loaded: dict[str, dict[str, Any]] = {}
    for specification in decision["inputs"]:
        path = (ROOT / specification["path"]).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ResearchDecisionError(f"missing input: {specification['path']}")
        if _hash(path) != specification["sha256"]:
            raise ResearchDecisionError(f"input hash changed: {specification['path']}")
        loaded[specification["path"]] = json.loads(path.read_text())

    product = decision["product_scope"]
    action = decision["action_research"]
    data = decision["data_boundaries"]
    if (
        product["observation_model"] != "HERD_STATE_S1"
        or product["transition_model"] != "HERD_TRANSITION_S1"
        or product["default_user_action"] != "HOLD"
        or product["operational_action_ratio"] != 0.0
        or action["admitted_profit_take_evidence_count"] != 0
        or action["admitted_reentry_evidence_count"] != 0
        or action["adoptable_action_candidate"] is not None
        or action["blind_holdout_access_count"] != 0
        or action["prospective_action_shadow_enabled"] is not False
        or data["survivorship_safe"] is not False
        or data["blind_holdout_eligible"] is not False
    ):
        raise ResearchDecisionError("unsupported model authority detected")

    reports = {item["candidate"]: loaded[item["report"]] for item in decision["candidate_decisions"]}
    if (
        reports["HERD_GIVEBACK_S1"]["passed"] is not False
        or reports["FINRA_RUSH_DTC_DIVERGENCE_V1"]["historical_gate_passed"] is not False
        or reports["SEC_13F_INCREMENTAL_CROWDING"]["decision"]
        != "KEEP_13F_AS_NON_DIRECTIONAL_CONTEXT_ONLY"
        or reports[
            "FORM4_TIMING_NONROUTINE_MULTI_OWNER_SALE_30D_AT_S1_RUSH_ENTRY"
        ]["passed"]
        is not False
    ):
        raise ResearchDecisionError("rejected candidate was promoted")

    rejected = set(catalog["chains"]["REJECTED"])
    required_rejected = {
        item["report"] for item in decision["candidate_decisions"]
    }
    if not required_rejected.issubset(rejected):
        missing = sorted(required_rejected - rejected)
        raise ResearchDecisionError(f"rejected reports misclassified: {missing}")
    if any(
        item["report"] in catalog["chains"]["ACTIVE"]
        for item in decision["candidate_decisions"]
    ):
        raise ResearchDecisionError("rejected report remains active")

    return {
        "decision_version": VERSION,
        "product_scope": "STATE_AND_TRANSITION_OBSERVATION",
        "rejected_candidates": len(decision["candidate_decisions"]),
        "adoptable_action_candidates": 0,
        "survivorship_safe": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
        "next_stage": decision["next_stage"]["id"],
    }


def load_and_validate() -> dict[str, Any]:
    return validate_decision(
        json.loads(DECISION_PATH.read_text()),
        json.loads(CATALOG_PATH.read_text()),
    )


if __name__ == "__main__":
    print(json.dumps(load_and_validate(), indent=2))
