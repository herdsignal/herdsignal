from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PRODUCT_SCOPE = ROOT / "data" / "herd" / "product_scope_contract_v1.json"
RESEARCH_DECISION = ROOT / "data" / "herd" / "research_decision_v5.json"
PRIOR_RESEARCH_DECISION = ROOT / "data" / "herd" / "research_decision_v4.json"
MODEL_STATUS = ROOT / "data" / "herd" / "model_establishment_status_v1.json"
ARTIFACT_CATALOG = ROOT / "data" / "herd" / "research_artifact_catalog_v2.json"
ACTION_HYPOTHESIS = ROOT / "data" / "herd" / "rush_negative_earnings_reaction_preregistration_v1.json"
ACTION_HYPOTHESIS_REPORT = ROOT / "data" / "reports" / "rush_negative_earnings_reaction_oos_v1.json"
HISTORICAL_SCREEN_REPORT = ROOT / "data" / "reports" / "ticker_disjoint_earnings_reaction_oos_v1.json"
PROSPECTIVE_GATE_REPORT = ROOT / "data" / "reports" / "rush_earnings_prospective_confirmation_gate_v1.json"
EXPANSION_REPORT = ROOT / "data" / "reports" / "ticker_disjoint_earnings_oos_expansion_v2.json"
EXPANSION_SEC_REPORT = ROOT / "data" / "reports" / "ticker_disjoint_sec_earnings_census_v2.json"
EXPANSION_OOS_REPORT = ROOT / "data" / "reports" / "ticker_disjoint_earnings_reaction_oos_v2.json"
EXPANSION_OOS_GATE = ROOT / "data" / "reports" / "ticker_disjoint_earnings_reaction_oos_v2_gate.json"
EVIDENCE_ADMISSION = ROOT / "data" / "herd" / "model_evidence_admission_v1.json"
BUSINESS_VETO_GATE = ROOT / "data" / "contracts" / "business_veto_prospective_gate_v1.json"
ACTION_AUTHORIZATION = ROOT / "data" / "contracts" / "operational_action_authorization_v1.json"
MARKET_SECTOR_CONTEXT = ROOT / "data" / "contracts" / "market_sector_context_v1.json"
BUSINESS_CONTEXT = ROOT / "data" / "contracts" / "operating_business_evidence_v1.json"
EXPECTATION_CONTEXT = ROOT / "data" / "contracts" / "operating_expectation_evidence_v1.json"
INFORMATION_CONTEXT = ROOT / "data" / "contracts" / "operating_information_change_evidence_v1.json"
PORTFOLIO_RISK_CONTEXT = ROOT / "data" / "contracts" / "operating_portfolio_risk_v1.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_current_state(root: Path = ROOT) -> dict[str, Any]:
    product = _load(root / PRODUCT_SCOPE.relative_to(ROOT))
    decision = _load(root / RESEARCH_DECISION.relative_to(ROOT))
    prior_decision = _load(root / PRIOR_RESEARCH_DECISION.relative_to(ROOT))
    model = _load(root / MODEL_STATUS.relative_to(ROOT))
    catalog = _load(root / ARTIFACT_CATALOG.relative_to(ROOT))
    hypothesis = _load(root / ACTION_HYPOTHESIS.relative_to(ROOT))
    hypothesis_report = _load(root / ACTION_HYPOTHESIS_REPORT.relative_to(ROOT))
    historical_screen = _load(root / HISTORICAL_SCREEN_REPORT.relative_to(ROOT))
    prospective_gate = _load(root / PROSPECTIVE_GATE_REPORT.relative_to(ROOT))
    expansion = _load(root / EXPANSION_REPORT.relative_to(ROOT))
    expansion_sec = _load(root / EXPANSION_SEC_REPORT.relative_to(ROOT))
    expansion_oos = _load(root / EXPANSION_OOS_REPORT.relative_to(ROOT))
    expansion_gate = _load(root / EXPANSION_OOS_GATE.relative_to(ROOT))
    admission = _load(root / EVIDENCE_ADMISSION.relative_to(ROOT))
    business_veto_gate = _load(root / BUSINESS_VETO_GATE.relative_to(ROOT))
    action_authorization = _load(root / ACTION_AUTHORIZATION.relative_to(ROOT))
    market_sector_context = _load(root / MARKET_SECTOR_CONTEXT.relative_to(ROOT))
    business_context = _load(root / BUSINESS_CONTEXT.relative_to(ROOT))
    expectation_context = _load(root / EXPECTATION_CONTEXT.relative_to(ROOT))
    information_context = _load(root / INFORMATION_CONTEXT.relative_to(ROOT))
    portfolio_risk_context = _load(root / PORTFOLIO_RISK_CONTEXT.relative_to(ROOT))

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
    if catalog_decision["canonical_decision"] != "data/herd/research_decision_v5.json":
        contradictions.append("artifact catalog points at a stale canonical decision")
    if product.get("research_prototypes") == ["SOURCE_GROUNDED_AI_EVIDENCE_REVIEW"]:
        if authority.get("ai_review_can_set_action") is not False:
            contradictions.append("AI evidence review unexpectedly has action authority")
        if authority.get("ai_review_can_create_evidence") is not False:
            contradictions.append("AI evidence review unexpectedly creates model evidence")
    if hypothesis["authority"]["operational_action_ratio"] != 0.0:
        contradictions.append("new action hypothesis unexpectedly has operational authority")
    if hypothesis_report["candidate_action_enabled"]:
        contradictions.append("waiting action hypothesis unexpectedly enabled an action")
    if hypothesis_report["direction_evidence_admitted"]:
        contradictions.append("waiting action hypothesis unexpectedly admitted direction evidence")
    if historical_screen["candidate_action_enabled"]:
        contradictions.append("failed historical screen unexpectedly enabled an action")
    if historical_screen["direction_evidence_admitted"]:
        contradictions.append("historical screen unexpectedly admitted direction evidence")
    if historical_screen["passed"] != prospective_gate["historical_screen_passed"]:
        contradictions.append("historical result and prospective gate disagree")
    if not historical_screen["passed"] and prospective_gate["prospective_outcomes_may_be_opened_when_mature"]:
        contradictions.append("prospective outcomes opened after a failed historical screen")
    if prospective_gate["operational_action_ratio"] != 0.0:
        contradictions.append("prospective gate unexpectedly has operational authority")
    if expansion["status"] != "EXPANSION_INPUT_READY":
        contradictions.append("former-constituent expansion input is not ready")
    if expansion_sec["status"] != "SEC_HISTORY_READY":
        contradictions.append("former-constituent SEC history is incomplete")
    if expansion_sec["covered_tickers"] != expansion["eligible_tickers"]:
        contradictions.append("former-constituent universe and SEC coverage disagree")
    if expansion_sec["operational_action_ratio"] != 0.0:
        contradictions.append("former-constituent SEC census unexpectedly has action authority")
    if expansion_oos["passed"] != expansion_gate["independent_historical_oos_passed"]:
        contradictions.append("former-constituent OOS result and gate disagree")
    if expansion_oos["combined_with_v1_for_gate"]:
        contradictions.append("independent former-constituent OOS was combined with V1")
    if expansion_oos["thresholds_retuned"]:
        contradictions.append("failed formula was retuned on the independent OOS")
    if expansion_gate["prospective_confirmation_allowed"]:
        contradictions.append("failed independent OOS unexpectedly opened prospective confirmation")
    if expansion_gate["operational_action_ratio"] != 0.0:
        contradictions.append("failed independent OOS unexpectedly has action authority")
    admission_summary = admission["admission_summary"]
    if admission_summary["direction_evidence_admitted"] != 0:
        contradictions.append("runtime admission registry unexpectedly admits trim direction")
    if admission_summary["reentry_support_admitted"] != 0:
        contradictions.append("runtime admission registry unexpectedly admits add direction")
    if admission_summary["business_veto_admitted"] != 0:
        contradictions.append("runtime admission registry unexpectedly admits business veto")
    if admission["claim_boundary"]["operational_action_ratio"] != 0.0:
        contradictions.append("runtime admission registry unexpectedly has action ratio")
    if business_veto_gate["current"]["collection_allowed"]:
        contradictions.append("business veto collection opened without prerequisites")
    if business_veto_gate["current"]["operational_action_ratio"] != 0.0:
        contradictions.append("business veto gate unexpectedly has action ratio")
    authorization_current = action_authorization["current"]
    if authorization_current["review_trim_authorized"]:
        contradictions.append("runtime authorization unexpectedly enables trim")
    if authorization_current["review_add_authorized"]:
        contradictions.append("runtime authorization unexpectedly enables add")
    if authorization_current["operational_action_ratio"] != 0.0:
        contradictions.append("runtime authorization unexpectedly has action ratio")
    if market_sector_context["authority"]["may_predict_direction"]:
        contradictions.append("market-sector context unexpectedly predicts direction")
    if market_sector_context["authority"]["may_change_herd_state"]:
        contradictions.append("market-sector context unexpectedly changes HERD state")
    if market_sector_context["authority"]["operational_action_ratio"] != 0.0:
        contradictions.append("market-sector context unexpectedly has action ratio")
    if business_context["authority"]["health_score"]:
        contradictions.append("business context unexpectedly creates a health score")
    if business_context["authority"]["direction_prediction"]:
        contradictions.append("business context unexpectedly predicts direction")
    if business_context["authority"]["add_buy_veto"]:
        contradictions.append("rejected business veto unexpectedly became operational")
    if business_context["authority"]["action_ratio"] != 0.0:
        contradictions.append("business context unexpectedly has action ratio")
    if expectation_context["authority"]["guidance_direction"]:
        contradictions.append("expectation context unexpectedly classifies guidance direction")
    if expectation_context["authority"]["consensus_surprise"]:
        contradictions.append("expectation context unexpectedly infers consensus surprise")
    if expectation_context["authority"]["valuation_judgment"]:
        contradictions.append("expectation context unexpectedly judges valuation")
    if expectation_context["authority"]["current_snapshot_valuation_as_pit"]:
        contradictions.append("current valuation snapshot unexpectedly became PIT evidence")
    if expectation_context["authority"]["action_ratio"] != 0.0:
        contradictions.append("expectation context unexpectedly has action ratio")
    if information_context["authority"]["direction_prediction"]:
        contradictions.append("information context unexpectedly predicts direction")
    if information_context["authority"]["aggregate_information_score"]:
        contradictions.append("information context unexpectedly aggregates a score")
    if information_context["authority"]["action_veto"]:
        contradictions.append("information context unexpectedly has a veto")
    if information_context["authority"]["action_ratio"] != 0.0:
        contradictions.append("information context unexpectedly has action ratio")
    if portfolio_risk_context["authority"]["infer_ticker_target_weight"]:
        contradictions.append("portfolio context unexpectedly infers a ticker target")
    if portfolio_risk_context["authority"]["classify_ticker_overweight_or_underweight"]:
        contradictions.append("portfolio context unexpectedly classifies ticker concentration")
    if portfolio_risk_context["authority"]["predict_action_direction"]:
        contradictions.append("portfolio context unexpectedly predicts action direction")
    if portfolio_risk_context["authority"]["operational_action_ratio"] != 0.0:
        contradictions.append("portfolio context unexpectedly has action ratio")

    pending_source_review = prior_decision["new_source_candidate"][
        "pending_source_decisions"
    ]
    return {
        "version": "HERDSIGNAL_CURRENT_STATE_AUDIT_V1",
        "as_of": decision["as_of"],
        "status": "PASS" if not contradictions else "FAIL",
        "product": {
            "scope": product["status"],
            "state_model": authority["state_model"],
            "state_observation_ready": True,
            "portfolio_and_journal_ready": True,
            "research_prototypes": product.get("research_prototypes", []),
        },
        "action_research": {
            "decision": model["overall_decision"],
            "total_locked_rejected_experiments": decision["action_research"][
                "total_locked_rejected_experiments"
            ],
            "promotion_candidate_rounds": decision["action_research"][
                "promotion_candidate_rounds"
            ],
            "adoptable_candidates": 0,
            "direction_evidence_admitted": model_facts["direction_evidence_admitted"],
            "default_action": authority["default_action"],
            "operational_action_ratio": authority["operational_action_ratio"],
            "blind_holdout_open": False,
            "survivorship_safe": decision["data_boundaries"]["survivorship_safe"],
        },
        "runtime_action_authority": {
            "registry_version": admission["registry_version"],
            "profit_take_direction_admitted": admission_summary[
                "direction_evidence_admitted"
            ],
            "reentry_support_admitted": admission_summary["reentry_support_admitted"],
            "business_veto_admitted": admission_summary["business_veto_admitted"],
            "business_veto_collection_allowed": business_veto_gate["current"][
                "collection_allowed"
            ],
            "review_trim_authorized": authorization_current["review_trim_authorized"],
            "review_add_authorized": authorization_current["review_add_authorized"],
            "operational_action_ratio": authorization_current[
                "operational_action_ratio"
            ],
        },
        "market_sector_context": {
            "schema_version": market_sector_context["schema_version"],
            "status": market_sector_context["status"],
            "direction_prediction": market_sector_context["authority"][
                "may_predict_direction"
            ],
            "changes_herd_state": market_sector_context["authority"][
                "may_change_herd_state"
            ],
            "operational_action_ratio": market_sector_context["authority"][
                "operational_action_ratio"
            ],
        },
        "business_health_context": {
            "schema_version": business_context["schema_version"],
            "status": business_context["status"],
            "presentation_groups": list(business_context["presentation_groups"].keys()),
            "health_score": business_context["authority"]["health_score"],
            "direction_prediction": business_context["authority"]["direction_prediction"],
            "add_buy_veto": business_context["authority"]["add_buy_veto"],
            "operational_action_ratio": business_context["authority"]["action_ratio"],
        },
        "expectation_valuation_context": {
            "schema_version": expectation_context["schema_version"],
            "status": expectation_context["status"],
            "connected_dimensions": expectation_context["connected_dimensions"],
            "explicit_no_view_dimensions": expectation_context[
                "explicit_no_view_dimensions"
            ],
            "guidance_direction": expectation_context["authority"]["guidance_direction"],
            "consensus_surprise": expectation_context["authority"]["consensus_surprise"],
            "valuation_judgment": expectation_context["authority"]["valuation_judgment"],
            "operational_action_ratio": expectation_context["authority"]["action_ratio"],
        },
        "information_change_context": {
            "schema_version": information_context["schema_version"],
            "status": information_context["status"],
            "sources": information_context["sources"],
            "direction_prediction": information_context["authority"][
                "direction_prediction"
            ],
            "aggregate_information_score": information_context["authority"][
                "aggregate_information_score"
            ],
            "operational_action_ratio": information_context["authority"][
                "action_ratio"
            ],
        },
        "portfolio_risk_context": {
            "schema_version": portfolio_risk_context["schema_version"],
            "status": portfolio_risk_context["status"],
            "portfolio_facts": portfolio_risk_context["portfolio_facts"],
            "risk_veto_sources": portfolio_risk_context["risk_veto_sources"],
            "ticker_target_inferred": portfolio_risk_context["authority"][
                "infer_ticker_target_weight"
            ],
            "action_direction": portfolio_risk_context["authority"][
                "predict_action_direction"
            ],
            "operational_action_ratio": portfolio_risk_context["authority"][
                "operational_action_ratio"
            ],
        },
        "research_boundary": {
            "canonical_decision": catalog_decision["canonical_decision"],
            "pending_sec_identity_reviews": pending_source_review,
            "sec_identity_work_role": prior_decision["new_source_candidate"]["allowed_role"],
            "sec_identity_work_unlocks_action_direction": False,
            "next_stage": decision["next_stage"]["id"],
            "required_outputs": decision["next_stage"]["required_outputs"],
            "forbidden": decision["next_stage"]["forbidden"],
        },
        "new_action_hypothesis": {
            "id": hypothesis["single_hypothesis"]["id"],
            "status": historical_screen["status"],
            "historical_screen": {
                "passed": historical_screen["passed"],
                "mature_events": historical_screen["mature_events"],
                "distinct_tickers": historical_screen["distinct_tickers"],
                "calendar_years": historical_screen["calendar_years"],
            },
            "prospective_status": prospective_gate["status"],
            "sec_collection_active": prospective_gate["sec_append_only_collection_active"],
            "prospective_outcomes_open": prospective_gate["prospective_outcomes_may_be_opened_when_mature"],
            "prospective_mature_events": hypothesis_report["mature_events"],
            "direction_evidence_admitted": historical_screen["direction_evidence_admitted"],
            "operational_action_ratio": prospective_gate["operational_action_ratio"],
        },
        "independent_expansion": {
            "status": expansion_sec["status"],
            "eligible_tickers": expansion["eligible_tickers"],
            "sec_covered_tickers": expansion_sec["covered_tickers"],
            "sec_events": expansion_sec["events"],
            "first_acceptance": expansion_sec["first_acceptance"],
            "last_acceptance": expansion_sec["last_acceptance"],
            "identity_corrections": expansion["sec_identity_corrections"],
            "historical_reaction_outcomes_opened": True,
            "oos_status": expansion_oos["status"],
            "mature_events": expansion_oos["mature_events"],
            "distinct_tickers": expansion_oos["distinct_tickers"],
            "median_terminal_wealth_delta": expansion_oos["median_terminal_wealth_delta"],
            "prospective_confirmation_allowed": expansion_gate["prospective_confirmation_allowed"],
        },
        "contradictions": contradictions,
    }


def main() -> int:
    state = build_current_state()
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0 if state["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
