"""Validate the current HERD decision without rewriting historical contracts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from herd.research_decision_v2 import load_and_validate as validate_v2


ROOT = Path(__file__).resolve().parents[2]
DECISION_PATH = Path(__file__).with_suffix(".json")
REPORT_PATH = ROOT / "data/reports/research_decision_v3.json"
CATALOG_PATH = Path(__file__).with_name("research_artifact_catalog_v2.json")
VERSION = "HERD_RESEARCH_DECISION_V3"


class ResearchDecisionV3Error(ValueError):
    """Raised when current action authority exceeds admitted evidence."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_inputs(decision: dict[str, Any]) -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = {}
    if len(decision.get("inputs", [])) != 7:
        raise ResearchDecisionV3Error("decision input set is incomplete")
    for specification in decision["inputs"]:
        path = (ROOT / specification["path"]).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ResearchDecisionV3Error(f"missing input: {specification['path']}")
        if _sha256(path) != specification.get("sha256"):
            raise ResearchDecisionV3Error(f"input hash changed: {specification['path']}")
        loaded[specification["path"]] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def validate_decision(
    decision: dict[str, Any], catalog: dict[str, Any]
) -> dict[str, Any]:
    if (
        decision.get("decision_version") != VERSION
        or decision.get("status")
        != "STATE_OBSERVATION_MVP_READY_NO_ACTION_CANDIDATE"
        or decision.get("supersedes_for_current_status")
        != "data/herd/research_decision_v2.json"
        or decision.get("preserves_prior_decisions_as_reproducibility_inputs")
        is not True
    ):
        raise ResearchDecisionV3Error("current decision boundary changed")

    loaded = _load_inputs(decision)
    prior = validate_v2()
    if prior["adoptable_action_candidates"] != 0:
        raise ResearchDecisionV3Error("prior decision unexpectedly admitted a candidate")

    product = decision.get("product_scope", {})
    research = decision.get("action_research", {})
    boundaries = decision.get("data_boundaries", {})
    if (
        product.get("observation_model") != "HERD_STATE_S1"
        or product.get("transition_model") != "HERD_TRANSITION_S1"
        or product.get("observation_display_ready") is not True
        or product.get("portfolio_and_journal_mvp_ready") is not True
        or product.get("default_user_action") != "HOLD"
        or product.get("operational_action_ratio") != 0.0
        or research.get("evaluated_candidate_count") != 5
        or research.get("admitted_profit_take_evidence_count") != 0
        or research.get("admitted_reentry_evidence_count") != 0
        or research.get("adoptable_action_candidate") is not None
        or research.get("blind_holdout_access_count") != 0
        or research.get("prospective_action_shadow_enabled") is not False
        or boundaries.get("survivorship_safe") is not False
        or boundaries.get("prospective_observation_collection_enabled") is not True
        or boundaries.get("prospective_action_shadow_enabled") is not False
        or boundaries.get("blind_holdout_eligible") is not False
    ):
        raise ResearchDecisionV3Error("unsupported model authority detected")

    latest = decision.get("latest_candidate", {})
    report_path = latest.get("report")
    report = loaded.get(report_path, {})
    if (
        latest.get("candidate")
        != "RUSH_MARGIN_CASH_DIVERGENCE_RELATIVE_REBALANCE_V1"
        or latest.get("decision") != "REJECTED_PREHOLDOUT_OOS"
        or latest.get("candidate_events") != 7
        or latest.get("candidate_tickers") != 5
        or latest.get("all_adoption_gates_passed") is not False
        or report.get("status") != "PREHOLDOUT_REJECTED_NO_ACTION_AUTHORITY"
        or report.get("candidates") != 7
        or report.get("candidate_tickers") != 5
        or report.get("all_adoption_gates_passed") is not False
        or report.get("direction_evidence_admitted") is not False
        or report.get("policy_promoted") is not False
        or report.get("operational_action_ratio") != 0.0
        or report.get("blind_holdout_access") is not False
    ):
        raise ResearchDecisionV3Error("latest rejected candidate was misrepresented")

    next_stage = decision.get("next_stage", {})
    if (
        next_stage.get("id") != "DISTINCT_PUBLIC_PIT_INFORMATION_FEASIBILITY_V1"
        or len(next_stage.get("required_checks", [])) != 6
        or set(next_stage.get("forbidden", []))
        != {
            "RETUNE_RUSH_MARGIN_CASH_DIVERGENCE",
            "COMBINE_REJECTED_FEATURES",
            "REGISTER_DIRECTION_HYPOTHESIS_BEFORE_COVERAGE_PASS",
            "OPEN_BLIND_HOLDOUT",
            "ENABLE_OPERATIONAL_ACTION",
        }
    ):
        raise ResearchDecisionV3Error("next research boundary changed")

    rejected = set(catalog["chains"]["REJECTED"])
    if report_path not in rejected or report_path in catalog["chains"]["ACTIVE"]:
        raise ResearchDecisionV3Error("latest rejected report is misclassified")
    if catalog.get("current_decision", {}).get("canonical_decision") != str(
        DECISION_PATH.relative_to(ROOT)
    ):
        raise ResearchDecisionV3Error("catalog does not point to decision V3")

    return {
        "decision_version": VERSION,
        "status": decision["status"],
        "product_scope": "STATE_AND_TRANSITION_OBSERVATION",
        "evaluated_candidates": research["evaluated_candidate_count"],
        "adoptable_action_candidates": 0,
        "latest_candidate_decision": latest["decision"],
        "survivorship_safe": False,
        "blind_holdout_access": False,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
        "next_stage": next_stage["id"],
    }


def load_and_validate() -> dict[str, Any]:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    # Reproduce V3 against its historical catalog pointer after newer decisions
    # become current. Explicit validate_decision calls remain strict.
    catalog["current_decision"]["canonical_decision"] = str(
        DECISION_PATH.relative_to(ROOT)
    )
    return validate_decision(
        json.loads(DECISION_PATH.read_text(encoding="utf-8")),
        catalog,
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
