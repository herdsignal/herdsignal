from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PRODUCT_SCOPE = ROOT / "data" / "herd" / "product_scope_contract_v1.json"
RESEARCH_DECISION = ROOT / "data" / "herd" / "research_decision_v4.json"
MODEL_STATUS = ROOT / "data" / "herd" / "model_establishment_status_v1.json"
ARTIFACT_CATALOG = ROOT / "data" / "herd" / "research_artifact_catalog_v2.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_current_state(root: Path = ROOT) -> dict[str, Any]:
    product = _load(root / PRODUCT_SCOPE.relative_to(ROOT))
    decision = _load(root / RESEARCH_DECISION.relative_to(ROOT))
    model = _load(root / MODEL_STATUS.relative_to(ROOT))
    catalog = _load(root / ARTIFACT_CATALOG.relative_to(ROOT))

    authority = product["authority"]
    product_decision = decision["product_scope"]
    model_facts = model["facts"]
    catalog_decision = catalog["current_decision"]

    contradictions: list[str] = []
    if authority["state_model"] != product_decision["observation_model"]:
        contradictions.append("state model differs between product and research decision")
    if authority["default_action"] != product_decision["default_user_action"]:
        contradictions.append("default action differs between product and research decision")
    ratios = {
        float(authority["operational_action_ratio"]),
        float(product_decision["operational_action_ratio"]),
        float(model_facts["operational_action_ratio"]),
        float(catalog_decision["operational_action_ratio"]),
    }
    if ratios != {0.0}:
        contradictions.append("operational action ratio is not consistently locked to zero")
    if decision["action_research"]["adoptable_action_candidate"] is not None:
        contradictions.append("research decision unexpectedly exposes an action candidate")
    if model_facts["direction_evidence_admitted"] != 0:
        contradictions.append("model status unexpectedly admits direction evidence")
    if decision["data_boundaries"]["blind_holdout_eligible"]:
        contradictions.append("blind holdout must remain closed")
    if catalog_decision["canonical_decision"] != "data/herd/research_decision_v4.json":
        contradictions.append("artifact catalog points at a stale canonical decision")
    if product.get("research_prototypes") == ["SOURCE_GROUNDED_AI_EVIDENCE_REVIEW"]:
        if authority.get("ai_review_can_set_action") is not False:
            contradictions.append("AI evidence review unexpectedly has action authority")
        if authority.get("ai_review_can_create_evidence") is not False:
            contradictions.append("AI evidence review unexpectedly creates model evidence")

    pending_source_review = decision["new_source_candidate"]["pending_source_decisions"]
    return {
        "version": "HERDSIGNAL_CURRENT_STATE_AUDIT_V1",
        "as_of": decision["as_of"],
        "status": "PASS" if not contradictions else "FAIL",
        "product": {
            "scope": product["status"],
            "state_model": authority["state_model"],
            "state_observation_ready": product_decision["observation_display_ready"],
            "portfolio_and_journal_ready": product_decision["portfolio_and_journal_mvp_ready"],
            "research_prototypes": product.get("research_prototypes", []),
        },
        "action_research": {
            "decision": model["overall_decision"],
            "evaluated_candidates": decision["action_research"]["evaluated_candidate_count"],
            "adoptable_candidates": 0,
            "direction_evidence_admitted": model_facts["direction_evidence_admitted"],
            "default_action": authority["default_action"],
            "operational_action_ratio": authority["operational_action_ratio"],
            "blind_holdout_open": False,
            "survivorship_safe": decision["data_boundaries"]["survivorship_safe"],
        },
        "research_boundary": {
            "canonical_decision": catalog_decision["canonical_decision"],
            "pending_sec_identity_reviews": pending_source_review,
            "sec_identity_work_role": decision["new_source_candidate"]["allowed_role"],
            "sec_identity_work_unlocks_action_direction": False,
            "next_allowed": model["next_research"]["allowed"],
            "forbidden": model["next_research"]["forbidden"],
        },
        "contradictions": contradictions,
    }


def main() -> int:
    state = build_current_state()
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0 if state["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
