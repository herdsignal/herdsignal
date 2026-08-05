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
AI_REVIEW_CONTEXT = ROOT / "data" / "contracts" / "ai_evidence_review_v2.json"
OPERATING_REVIEW_LEDGER = ROOT / "data" / "contracts" / "operating_review_ledger_v1.json"
FAILED_ACTION_SYNTHESIS = ROOT / "data" / "reports" / "failed_action_research_synthesis_v1.json"
EVIDENCE_ROLE_AUDIT = ROOT / "data" / "reports" / "independent_evidence_role_audit_v1.json"
RUNTIME_ROLE_MAPPING = ROOT / "data" / "reports" / "runtime_evidence_role_mapping_v1.json"
SOURCE_GAP_PRIORITY = ROOT / "data" / "reports" / "role_specific_source_gap_priority_v1.json"
SEC_8K_REVIEW_BATCHING = ROOT / "data" / "reports" / "sec_8k_material_event_review_batching_v1.json"
SEC_8K_EXTRACTION_FAILURE_AUDIT = ROOT / "data" / "reports" / "sec_8k_identity_extraction_failure_audit_v1.json"
SEC_8K_STRUCTURAL_EXTRACTOR = ROOT / "data" / "reports" / "sec_8k_structural_cover_extractor_v2.json"
SEC_8K_STRUCTURAL_REVIEW = ROOT / "data" / "reports" / "sec_8k_structural_candidate_review_v1.json"
SEC_8K_STRUCTURAL_EXPANSION = ROOT / "data" / "reports" / "sec_8k_structural_evaluation_expansion_v1.json"


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
    ai_review_context = _load(root / AI_REVIEW_CONTEXT.relative_to(ROOT))
    operating_review_ledger = _load(root / OPERATING_REVIEW_LEDGER.relative_to(ROOT))
    failed_action_synthesis = _load(root / FAILED_ACTION_SYNTHESIS.relative_to(ROOT))
    evidence_role_audit = _load(root / EVIDENCE_ROLE_AUDIT.relative_to(ROOT))
    runtime_role_mapping = _load(root / RUNTIME_ROLE_MAPPING.relative_to(ROOT))
    source_gap_priority = _load(root / SOURCE_GAP_PRIORITY.relative_to(ROOT))
    sec_8k_review_batching = _load(root / SEC_8K_REVIEW_BATCHING.relative_to(ROOT))
    sec_8k_failure_audit = _load(root / SEC_8K_EXTRACTION_FAILURE_AUDIT.relative_to(ROOT))
    sec_8k_structural_extractor = _load(root / SEC_8K_STRUCTURAL_EXTRACTOR.relative_to(ROOT))
    sec_8k_structural_review = _load(root / SEC_8K_STRUCTURAL_REVIEW.relative_to(ROOT))
    sec_8k_structural_expansion = _load(root / SEC_8K_STRUCTURAL_EXPANSION.relative_to(ROOT))

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
    if not ai_review_context["validation"]["server_side_area_isolation"]:
        contradictions.append("AI review does not isolate evidence areas")
    if ai_review_context["privacy"]["portfolio_data_sent"]:
        contradictions.append("AI review unexpectedly sends private portfolio data")
    if ai_review_context["authority"]["create_evidence"]:
        contradictions.append("AI review unexpectedly creates evidence")
    if ai_review_context["authority"]["predict_direction"]:
        contradictions.append("AI review unexpectedly predicts direction")
    if ai_review_context["authority"]["set_action"]:
        contradictions.append("AI review unexpectedly sets action")
    if ai_review_context["authority"]["operational_action_ratio"] != 0.0:
        contradictions.append("AI review unexpectedly has action ratio")
    if operating_review_ledger["mismatch_policy"]["outcome_attribution_allowed"]:
        contradictions.append("corrupted operating records unexpectedly allow attribution")
    if operating_review_ledger["legacy_policy"]["existing_rows_are_backfilled"]:
        contradictions.append("legacy operating records were unexpectedly re-signed")
    if operating_review_ledger["authority"]["creates_direction_evidence"]:
        contradictions.append("operating review ledger unexpectedly creates direction evidence")
    if operating_review_ledger["authority"]["authorizes_action"]:
        contradictions.append("operating review ledger unexpectedly authorizes action")
    if operating_review_ledger["authority"]["operational_action_ratio"] != 0.0:
        contradictions.append("operating review ledger unexpectedly has action ratio")
    if failed_action_synthesis["next_stage"]["new_hypothesis_allowed"]:
        contradictions.append("failure synthesis unexpectedly permits a new hypothesis")
    if failed_action_synthesis["target_validity_audit"]["target_is_currently_separable"]:
        contradictions.append("failure synthesis unexpectedly marks the action target separable")
    if failed_action_synthesis["operational_action_ratio"] != 0.0:
        contradictions.append("failure synthesis unexpectedly has action authority")
    if evidence_role_audit["summary"]["directional_vote_roles"] != 0:
        contradictions.append("evidence role audit unexpectedly admits a directional vote")
    if evidence_role_audit["architecture_decision"]["majority_vote_allowed"]:
        contradictions.append("evidence role audit unexpectedly permits majority voting")
    if evidence_role_audit["operational_action_ratio"] != 0.0:
        contradictions.append("evidence role audit unexpectedly has action authority")
    if runtime_role_mapping["directional_vote_roles"] != 0:
        contradictions.append("runtime role mapping unexpectedly admits a directional vote")
    if runtime_role_mapping["architecture_decision"]["portfolio_sent_to_ai"]:
        contradictions.append("runtime role mapping unexpectedly sends portfolio data to AI")
    if runtime_role_mapping["architecture_decision"]["committee_or_agent_label_allowed"]:
        contradictions.append("runtime roles are mislabeled as committee agents")
    if runtime_role_mapping["operational_action_ratio"] != 0.0:
        contradictions.append("runtime role mapping unexpectedly has action authority")
    if source_gap_priority["summary"]["direction_ready_sources"] != 0:
        contradictions.append("source gap priority unexpectedly finds direction-ready evidence")
    if source_gap_priority["new_hypothesis_allowed"]:
        contradictions.append("source gap priority unexpectedly opens a new hypothesis")
    if source_gap_priority["operational_action_ratio"] != 0.0:
        contradictions.append("source gap priority unexpectedly has action authority")
    if sec_8k_review_batching["auto_labels_created"] != 0:
        contradictions.append("SEC 8-K batching unexpectedly auto-labels source evidence")
    if sec_8k_review_batching["identity_promotion_allowed"]:
        contradictions.append("pending SEC 8-K batches unexpectedly promote identity")
    if sec_8k_review_batching["operational_action_ratio"] != 0.0:
        contradictions.append("SEC 8-K batching unexpectedly has action authority")
    if not sec_8k_failure_audit["all_invalids_are_markup_tokens"]:
        contradictions.append("SEC 8-K extraction failures remain unclassified")
    if sec_8k_failure_audit["identity_promotion_allowed"]:
        contradictions.append("SEC 8-K failure audit unexpectedly promotes identity")
    if sec_8k_structural_extractor["development_regression_passed"] != 110:
        contradictions.append("SEC 8-K structural extractor regression failed")
    if sec_8k_structural_extractor["identity_promotion_allowed"]:
        contradictions.append("SEC 8-K structural extractor unexpectedly promotes identity")
    if sec_8k_structural_extractor["operational_action_ratio"] != 0.0:
        contradictions.append("SEC 8-K structural extractor unexpectedly has action authority")
    if sec_8k_structural_review["development_rows_pooled"] != 0:
        contradictions.append("SEC 8-K structural review pools development labels")
    if sec_8k_structural_review["identity_promotion_allowed"]:
        contradictions.append("undersized SEC 8-K structural review promotes identity")
    if sec_8k_structural_review["operational_action_ratio"] != 0.0:
        contradictions.append("SEC 8-K structural review unexpectedly has action authority")
    if sec_8k_structural_expansion["development_accession_overlap"] != 0:
        contradictions.append("SEC 8-K evaluation expansion overlaps development data")
    if sec_8k_structural_expansion["canonical_symbols_exposed"] != 0:
        contradictions.append("SEC 8-K evaluation queue exposes known ticker labels")
    if sec_8k_structural_expansion["identity_promotion_allowed"]:
        contradictions.append("unreviewed SEC 8-K evaluation queue promotes identity")
    if sec_8k_structural_expansion["operational_action_ratio"] != 0.0:
        contradictions.append("SEC 8-K evaluation queue unexpectedly has action authority")

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
        "ai_evidence_review": {
            "schema_version": ai_review_context["schema_version"],
            "status": ai_review_context["status"],
            "scope": ai_review_context["scope"],
            "lenses": list(ai_review_context["lenses"].keys()),
            "area_isolation": ai_review_context["validation"][
                "server_side_area_isolation"
            ],
            "portfolio_data_sent": ai_review_context["privacy"][
                "portfolio_data_sent"
            ],
            "creates_evidence": ai_review_context["authority"]["create_evidence"],
            "direction_prediction": ai_review_context["authority"]["predict_direction"],
            "operational_action_ratio": ai_review_context["authority"][
                "operational_action_ratio"
            ],
        },
        "operating_review_ledger": {
            "schema_version": operating_review_ledger["schema_version"],
            "status": operating_review_ledger["status"],
            "ledger_hash_version": operating_review_ledger["ledger_hash_version"],
            "integrity_statuses": operating_review_ledger["integrity_statuses"],
            "mismatch_outcome_attribution": operating_review_ledger[
                "mismatch_policy"
            ]["outcome_attribution_allowed"],
            "legacy_backfilled": operating_review_ledger["legacy_policy"][
                "existing_rows_are_backfilled"
            ],
            "creates_direction_evidence": operating_review_ledger["authority"][
                "creates_direction_evidence"
            ],
            "operational_action_ratio": operating_review_ledger["authority"][
                "operational_action_ratio"
            ],
        },
        "failed_action_synthesis": {
            "report_version": failed_action_synthesis["report_version"],
            "status": failed_action_synthesis["status"],
            "economic_opportunity_exists": failed_action_synthesis[
                "target_validity_audit"
            ]["economic_opportunity_exists"],
            "target_is_currently_separable": failed_action_synthesis[
                "target_validity_audit"
            ]["target_is_currently_separable"],
            "locked_rejected_experiments": failed_action_synthesis[
                "economic_family_redundancy_audit"
            ]["locked_rejected_experiments"],
            "fixed_policy_floor_passed": failed_action_synthesis[
                "policy_opportunity_cost_audit"
            ]["all_non_control_medians_non_negative"],
            "historical_direction_source_ready_count": failed_action_synthesis[
                "distinct_information_availability_decision"
            ]["historical_direction_source_ready_count"],
            "new_hypothesis_allowed": failed_action_synthesis["next_stage"][
                "new_hypothesis_allowed"
            ],
            "operational_action_ratio": failed_action_synthesis[
                "operational_action_ratio"
            ],
        },
        "independent_evidence_roles": {
            "report_version": evidence_role_audit["report_version"],
            "status": evidence_role_audit["status"],
            "role_count": evidence_role_audit["summary"]["role_count"],
            "directional_vote_roles": evidence_role_audit["summary"][
                "directional_vote_roles"
            ],
            "price_domain_roles": evidence_role_audit["summary"][
                "price_domain_roles"
            ],
            "pit_news_connected": evidence_role_audit["summary"][
                "pit_news_connected"
            ],
            "call_roles_ai_agents": evidence_role_audit["architecture_decision"][
                "call_roles_ai_agents"
            ],
            "majority_vote_allowed": evidence_role_audit["architecture_decision"][
                "majority_vote_allowed"
            ],
            "operational_action_ratio": evidence_role_audit[
                "operational_action_ratio"
            ],
        },
        "runtime_evidence_roles": {
            "report_version": runtime_role_mapping["report_version"],
            "status": runtime_role_mapping["status"],
            "role_count": runtime_role_mapping["role_count"],
            "objective_fact_roles": runtime_role_mapping["objective_fact_roles"],
            "status_only_roles": runtime_role_mapping["status_only_roles"],
            "private_after_objective_roles": runtime_role_mapping[
                "private_after_objective_roles"
            ],
            "directional_vote_roles": runtime_role_mapping["directional_vote_roles"],
            "committee_or_agent_label_allowed": runtime_role_mapping[
                "architecture_decision"
            ]["committee_or_agent_label_allowed"],
            "portfolio_sent_to_ai": runtime_role_mapping[
                "architecture_decision"
            ]["portfolio_sent_to_ai"],
            "operational_action_ratio": runtime_role_mapping[
                "operational_action_ratio"
            ],
        },
        "source_gap_priority": {
            "report_version": source_gap_priority["report_version"],
            "status": source_gap_priority["status"],
            "direction_ready_sources": source_gap_priority["summary"][
                "direction_ready_sources"
            ],
            "bounded_manual_review_sources": source_gap_priority["summary"][
                "bounded_manual_review_sources"
            ],
            "prospective_collection_only_sources": source_gap_priority["summary"][
                "prospective_collection_only_sources"
            ],
            "deferred_sources": source_gap_priority["summary"]["deferred_sources"],
            "stopped_direction_sources": source_gap_priority["summary"][
                "stopped_direction_sources"
            ],
            "selected_next_part": source_gap_priority["selected_next_part"]["id"],
            "operational_action_ratio": source_gap_priority[
                "operational_action_ratio"
            ],
        },
        "sec_8k_review_batches": {
            "report_version": sec_8k_review_batching["report_version"],
            "status": sec_8k_review_batching["status"],
            "rows": sec_8k_review_batching["rows"],
            "batch_size": sec_8k_review_batching["batch_size"],
            "batch_count": sec_8k_review_batching["batch_count"],
            "next_pending_batch": sec_8k_review_batching["next_pending_batch"],
            "auto_labels_created": sec_8k_review_batching["auto_labels_created"],
            "identity_promotion_allowed": sec_8k_review_batching[
                "identity_promotion_allowed"
            ],
            "operational_action_ratio": sec_8k_review_batching[
                "operational_action_ratio"
            ],
        },
        "sec_8k_structural_extraction": {
            "failure_audit_status": sec_8k_failure_audit["status"],
            "invalid_rows": sec_8k_failure_audit["invalid_rows"],
            "markup_false_positive_rows": sec_8k_failure_audit["error_families"].get(
                "HTML_ELEMENT_NAME_CAPTURED_AS_SYMBOL", 0
            ),
            "status": sec_8k_structural_extractor["status"],
            "development_regression_passed": sec_8k_structural_extractor[
                "development_regression_passed"
            ],
            "unseen_candidate_rows": sec_8k_structural_extractor[
                "unseen_candidate_rows"
            ],
            "unseen_review_status": sec_8k_structural_review["status"],
            "unseen_reviewed_rows": sec_8k_structural_review["reviewed_rows"],
            "unseen_valid_rows": sec_8k_structural_review["decision_counts"].get(
                "VALID", 0
            ),
            "unseen_wilson_95_lower_bound": sec_8k_structural_review[
                "wilson_95_lower_bound"
            ],
            "independent_evaluation_queue_status": sec_8k_structural_expansion[
                "status"
            ],
            "independent_evaluation_documents": sec_8k_structural_expansion[
                "documents"
            ],
            "independent_evaluation_issuers": sec_8k_structural_expansion[
                "issuers"
            ],
            "development_accession_overlap": sec_8k_structural_expansion[
                "development_accession_overlap"
            ],
            "identity_promotion_allowed": sec_8k_structural_extractor[
                "identity_promotion_allowed"
            ],
            "operational_action_ratio": sec_8k_structural_extractor[
                "operational_action_ratio"
            ],
        },
        "research_boundary": {
            "canonical_decision": catalog_decision["canonical_decision"],
            "pending_sec_identity_reviews": sum(
                batch["pending"] for batch in sec_8k_review_batching["batches"]
            ),
            "sec_identity_work_role": prior_decision["new_source_candidate"]["allowed_role"],
            "sec_identity_work_unlocks_action_direction": False,
            "completed_stage": decision["next_stage"]["id"],
            "next_stage": (
                "COMPLETE_SEC_8K_HUMAN_REVIEW_BATCH_"
                + sec_8k_review_batching["next_pending_batch"]
                if sec_8k_review_batching["next_pending_batch"]
                else sec_8k_structural_expansion["next_stage"]
            ),
            "required_outputs": [],
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
