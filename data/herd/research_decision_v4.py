"""Validate the current HERD boundary after the SEC source-coverage phase."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from herd.research_decision_v3 import load_and_validate as validate_v3


ROOT = Path(__file__).resolve().parents[2]
DECISION_PATH = Path(__file__).with_suffix(".json")
REPORT_PATH = ROOT / "data/reports/research_decision_v4.json"
CATALOG_PATH = Path(__file__).with_name("research_artifact_catalog_v2.json")
VERSION = "HERD_RESEARCH_DECISION_V4"


class ResearchDecisionV4Error(ValueError):
    """Raised when source readiness is overstated as action evidence."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_inputs(decision: dict[str, Any]) -> dict[str, dict[str, Any]]:
    specifications = decision.get("inputs", [])
    if len(specifications) != 5:
        raise ResearchDecisionV4Error("decision input set is incomplete")

    loaded: dict[str, dict[str, Any]] = {}
    for specification in specifications:
        path = (ROOT / specification["path"]).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ResearchDecisionV4Error(f"missing input: {specification['path']}")
        if _sha256(path) != specification.get("sha256"):
            raise ResearchDecisionV4Error(f"input hash changed: {specification['path']}")
        loaded[specification["path"]] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def validate_decision(
    decision: dict[str, Any], catalog: dict[str, Any]
) -> dict[str, Any]:
    if (
        decision.get("decision_version") != VERSION
        or decision.get("status")
        != "STATE_OBSERVATION_MVP_READY_ACTION_RESEARCH_SOURCE_REVIEW_BLOCKED"
        or decision.get("supersedes_for_current_status")
        != "data/herd/research_decision_v3.json"
        or decision.get("preserves_prior_decisions_as_reproducibility_inputs")
        is not True
    ):
        raise ResearchDecisionV4Error("current decision boundary changed")

    loaded = _load_inputs(decision)
    prior = validate_v3()
    if prior["adoptable_action_candidates"] != 0:
        raise ResearchDecisionV4Error("prior decision unexpectedly admitted a candidate")

    feasibility = loaded[
        "data/reports/distinct_public_pit_information_feasibility_v1.json"
    ]
    corpus = loaded["data/reports/sec_8k_hard_adverse_event_corpus_v1.json"]
    collection = loaded[
        "data/reports/sec_8k_identity_primary_document_collection_v1.json"
    ]
    review = loaded["data/reports/sec_8k_identity_source_review_v1.json"]
    source = decision.get("new_source_candidate", {})
    if (
        feasibility.get("coverage_passed") is not True
        or feasibility.get("direction_hypothesis_allowed") is not False
        or corpus.get("source_event_count") != 947
        or corpus.get("time_valid_mapped_events") != 185
        or corpus.get("unmapped_event_count") != 760
        or corpus.get("ambiguous_event_count") != 2
        or corpus.get("identity_linkage_passed") is not False
        or collection.get("collected_documents") != 275
        or collection.get("candidate_symbol_rows") != 110
        or collection.get("candidate_symbols_promoted") != 0
        or review.get("candidate_rows") != 110
        or review.get("decision_counts") != {"PENDING": 110}
        or review.get("approved_identity_rows") != 0
        or review.get("identity_promotion_allowed") is not False
        or source.get("allowed_role") != "CORPORATE_DAMAGE_VETO_RESEARCH_ONLY"
        or source.get("coverage_passed") is not True
        or source.get("identity_linkage_passed") is not False
        or source.get("pending_source_decisions") != 110
        or source.get("direction_hypothesis_allowed") is not False
    ):
        raise ResearchDecisionV4Error("SEC source readiness was misrepresented")

    product = decision.get("product_scope", {})
    research = decision.get("action_research", {})
    boundaries = decision.get("data_boundaries", {})
    if (
        product.get("observation_model") != "HERD_STATE_S1"
        or product.get("transition_model") != "HERD_TRANSITION_S1"
        or product.get("default_user_action") != "HOLD"
        or product.get("operational_action_ratio") != 0.0
        or research.get("evaluated_candidate_count") != 5
        or research.get("admitted_profit_take_evidence_count") != 0
        or research.get("admitted_reentry_evidence_count") != 0
        or research.get("adoptable_action_candidate") is not None
        or research.get("blind_holdout_access_count") != 0
        or research.get("prospective_action_shadow_enabled") is not False
        or boundaries.get("survivorship_safe") is not False
        or boundaries.get("prospective_action_shadow_enabled") is not False
        or boundaries.get("blind_holdout_eligible") is not False
    ):
        raise ResearchDecisionV4Error("unsupported model authority detected")

    next_stage = decision.get("next_stage", {})
    if (
        next_stage.get("id") != "COMPLETE_110_SEC_IDENTITY_SOURCE_DECISIONS"
        or next_stage.get("promotion_checks")
        != {
            "minimum_reviewed_rows": 100,
            "minimum_wilson_95_lower_bound": 0.9,
            "maximum_ambiguous_ratio": 0.1,
            "all_candidate_rows_adjudicated": True,
        }
        or set(next_stage.get("forbidden", []))
        != {
            "AUTO_APPROVE_EXTRACTED_SYMBOLS",
            "BACKFILL_CURRENT_TICKER_INTO_HISTORY",
            "USE_EVENT_AS_DIRECT_BUY_OR_SELL_SIGNAL",
            "OPEN_PRICE_OUTCOMES_BEFORE_IDENTITY_GATE",
            "OPEN_BLIND_HOLDOUT",
            "ENABLE_OPERATIONAL_ACTION",
        }
    ):
        raise ResearchDecisionV4Error("next research boundary changed")

    if catalog.get("current_decision", {}).get("canonical_decision") != str(
        DECISION_PATH.relative_to(ROOT)
    ):
        raise ResearchDecisionV4Error("catalog does not point to decision V4")

    active = set(catalog["chains"]["ACTIVE"])
    if str(DECISION_PATH.relative_to(ROOT)) not in active:
        raise ResearchDecisionV4Error("decision V4 is not active")

    return {
        "decision_version": VERSION,
        "status": decision["status"],
        "product_scope": "STATE_AND_TRANSITION_OBSERVATION",
        "evaluated_candidates": 5,
        "adoptable_action_candidates": 0,
        "new_source_candidate": source["candidate"],
        "source_coverage_passed": True,
        "identity_linkage_passed": False,
        "pending_source_decisions": 110,
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
