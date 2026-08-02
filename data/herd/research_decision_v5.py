"""Lock the post-hypothesis research boundary and remove count ambiguity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from herd.failed_hypothesis_map_v2 import validate_failed_hypothesis_map_v2
from herd.research_decision_v4 import validate_decision as validate_v4


ROOT = Path(__file__).resolve().parents[2]
DECISION_PATH = Path(__file__).with_suffix(".json")
REPORT_PATH = ROOT / "data/reports/research_decision_v5.json"
CATALOG_PATH = Path(__file__).with_name("research_artifact_catalog_v2.json")
VERSION = "HERD_RESEARCH_DECISION_V5"


class ResearchDecisionV5Error(ValueError):
    """Raised when failed research is promoted or its accounting is weakened."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_inputs(decision: dict[str, Any]) -> dict[str, dict[str, Any]]:
    specifications = decision.get("inputs", [])
    if len(specifications) != 3:
        raise ResearchDecisionV5Error("decision input set is incomplete")
    loaded: dict[str, dict[str, Any]] = {}
    for specification in specifications:
        path = (ROOT / specification["path"]).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ResearchDecisionV5Error(f"missing input: {specification['path']}")
        if _sha256(path) != specification.get("sha256"):
            raise ResearchDecisionV5Error(f"input hash changed: {specification['path']}")
        loaded[specification["path"]] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def validate_decision(
    decision: dict[str, Any], catalog: dict[str, Any]
) -> dict[str, Any]:
    if (
        decision.get("decision_version") != VERSION
        or decision.get("status")
        != "STATE_OBSERVATION_MVP_READY_ACTION_EVIDENCE_EXHAUSTED"
        or decision.get("supersedes_for_current_status")
        != "data/herd/research_decision_v4.json"
        or decision.get("preserves_prior_decisions_as_reproducibility_inputs")
        is not True
    ):
        raise ResearchDecisionV5Error("current decision boundary changed")

    loaded = _load_inputs(decision)
    prior_catalog = json.loads(json.dumps(catalog))
    prior_catalog["current_decision"]["canonical_decision"] = (
        "data/herd/research_decision_v4.json"
    )
    if (
        validate_v4(
            loaded["data/herd/research_decision_v4.json"], prior_catalog
        )["adoptable_action_candidates"]
        != 0
    ):
        raise ResearchDecisionV5Error("prior decision admitted an action candidate")
    failure_audit = validate_failed_hypothesis_map_v2(
        loaded["data/herd/failed_hypothesis_map_v2.json"]
    )
    gate = loaded[
        "data/reports/ticker_disjoint_earnings_reaction_oos_v2_gate.json"
    ]
    if (
        failure_audit["experiment_count"] != 11
        or failure_audit["rejected_count"] != 11
        or failure_audit["adoptable_direction_count"] != 0
        or gate.get("status") != "HYPOTHESIS_REJECTED_NO_PROSPECTIVE_PROMOTION"
        or gate.get("prospective_confirmation_allowed") is not False
        or gate.get("operational_action_ratio") != 0.0
    ):
        raise ResearchDecisionV5Error("latest rejected evidence was misrepresented")

    product = decision.get("product_scope", {})
    research = decision.get("action_research", {})
    latest = decision.get("latest_hypothesis", {})
    boundaries = decision.get("data_boundaries", {})
    if (
        product.get("observation_model") != "HERD_STATE_S1"
        or product.get("transition_model") != "HERD_TRANSITION_S1"
        or product.get("default_user_action") != "HOLD"
        or product.get("operational_action_ratio") != 0.0
        or research.get("total_locked_rejected_experiments") != 11
        or research.get("promotion_candidate_rounds") != 6
        or research.get("admitted_profit_take_evidence_count") != 0
        or research.get("admitted_reentry_evidence_count") != 0
        or research.get("adoptable_action_candidate") is not None
        or research.get("blind_holdout_access_count") != 0
        or research.get("prospective_action_shadow_enabled") is not False
        or latest.get("status") != "INDEPENDENT_HISTORICAL_OOS_FAILED"
        or latest.get("same_sample_retuning_allowed") is not False
        or latest.get("sample_pooling_allowed") is not False
        or latest.get("prospective_confirmation_allowed") is not False
        or boundaries.get("survivorship_safe") is not False
        or boundaries.get("blind_holdout_eligible") is not False
        or boundaries.get("operational_action_enabled") is not False
    ):
        raise ResearchDecisionV5Error("unsupported action authority detected")

    next_stage = decision.get("next_stage", {})
    if (
        next_stage.get("id")
        != "SYNTHESIZE_FAILED_HYPOTHESES_BEFORE_NEW_DIRECTION_RESEARCH"
        or set(next_stage.get("required_outputs", []))
        != {
            "TARGET_VALIDITY_AUDIT",
            "ECONOMIC_FAMILY_REDUNDANCY_AUDIT",
            "POLICY_OPPORTUNITY_COST_AUDIT",
            "DISTINCT_INFORMATION_AVAILABILITY_DECISION",
        }
        or "ENABLE_OPERATIONAL_ACTION" not in next_stage.get("forbidden", [])
    ):
        raise ResearchDecisionV5Error("next research boundary changed")

    relative = str(DECISION_PATH.relative_to(ROOT))
    if catalog.get("current_decision", {}).get("canonical_decision") != relative:
        raise ResearchDecisionV5Error("catalog does not point to decision V5")
    if relative not in set(catalog["chains"]["ACTIVE"]):
        raise ResearchDecisionV5Error("decision V5 is not active")

    return {
        "decision_version": VERSION,
        "status": decision["status"],
        "product_scope": "STATE_AND_TRANSITION_OBSERVATION",
        "total_locked_rejected_experiments": 11,
        "promotion_candidate_rounds": 6,
        "adoptable_action_candidates": 0,
        "survivorship_safe": False,
        "blind_holdout_access": False,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
        "next_stage": next_stage["id"],
    }


def load_and_validate() -> dict[str, Any]:
    return validate_decision(
        json.loads(DECISION_PATH.read_text(encoding="utf-8")),
        json.loads(CATALOG_PATH.read_text(encoding="utf-8")),
    )


def run(report_path: Path = REPORT_PATH) -> dict[str, Any]:
    result = load_and_validate()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
