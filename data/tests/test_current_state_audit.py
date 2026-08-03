from pathlib import Path

from tools.current_state_audit import build_current_state


ROOT = Path(__file__).resolve().parents[2]


def test_current_state_contracts_are_consistent() -> None:
    state = build_current_state(ROOT)

    assert state["status"] == "PASS"
    assert state["product"]["state_model"] == "HERD_STATE_S1"
    assert state["action_research"]["adoptable_candidates"] == 0
    assert state["action_research"]["total_locked_rejected_experiments"] == 11
    assert state["action_research"]["promotion_candidate_rounds"] == 6
    assert state["action_research"]["operational_action_ratio"] == 0.0
    assert state["action_research"]["blind_holdout_open"] is False
    assert state["runtime_action_authority"] == {
        "registry_version": "HERD_MODEL_EVIDENCE_ADMISSION_V1",
        "profit_take_direction_admitted": 0,
        "reentry_support_admitted": 0,
        "business_veto_admitted": 0,
        "business_veto_collection_allowed": False,
        "review_trim_authorized": False,
        "review_add_authorized": False,
        "operational_action_ratio": 0.0,
    }
    assert state["market_sector_context"] == {
        "schema_version": "HERD_MARKET_SECTOR_CONTEXT_V1",
        "status": "ACTIVE_CONTEXT_ONLY",
        "direction_prediction": False,
        "changes_herd_state": False,
        "operational_action_ratio": 0.0,
    }
    assert state["business_health_context"] == {
        "schema_version": "HERD_OPERATING_BUSINESS_EVIDENCE_V1",
        "status": "OBSERVATION_ONLY",
        "presentation_groups": [
            "GROWTH",
            "PROFITABILITY",
            "CASH_GENERATION",
            "FINANCIAL_STRUCTURE",
        ],
        "health_score": False,
        "direction_prediction": False,
        "add_buy_veto": False,
        "operational_action_ratio": 0.0,
    }
    assert state["expectation_valuation_context"] == {
        "schema_version": "HERD_OPERATING_EXPECTATION_EVIDENCE_V1",
        "status": "OBSERVATION_ONLY",
        "connected_dimensions": ["MANAGEMENT_GUIDANCE_ATOMIC_FACT"],
        "explicit_no_view_dimensions": [
            "ANALYST_CONSENSUS",
            "POINT_IN_TIME_VALUATION",
        ],
        "guidance_direction": False,
        "consensus_surprise": False,
        "valuation_judgment": False,
        "operational_action_ratio": 0.0,
    }
    assert state["information_change_context"] == {
        "schema_version": "HERD_OPERATING_INFORMATION_CHANGE_EVIDENCE_V1",
        "status": "NO_VIEW_FAIL_CLOSED",
        "sources": {
            "SEC_MATERIAL_EVENT": "IDENTITY_AND_SOURCE_REVIEW_INCOMPLETE",
            "SEC_FORM4": "DIRECTION_HYPOTHESIS_REJECTED",
            "FINRA_SHORT_INTEREST": "PROSPECTIVE_SHADOW_ONLY",
            "SEC_13F": "DELAYED_CONTEXT_ONLY",
            "POINT_IN_TIME_NEWS": "NOT_CONNECTED",
        },
        "direction_prediction": False,
        "aggregate_information_score": False,
        "operational_action_ratio": 0.0,
    }
    assert state["portfolio_risk_context"] == {
        "schema_version": "HERD_OPERATING_PORTFOLIO_RISK_V1",
        "status": "OBSERVATION_ONLY_FAIL_CLOSED",
        "portfolio_facts": [
            "CURRENT_TICKER_WEIGHT",
            "CURRENT_EQUITY_RATIO",
            "CURRENT_CASH_RATIO",
            "TARGET_EQUITY_RATIO",
            "EQUITY_TARGET_GAP",
        ],
        "risk_veto_sources": [
            "DATA_GATE",
            "BUSINESS_EVIDENCE_AVAILABILITY",
            "DIRECTION_EVIDENCE_ADMISSION",
            "PORTFOLIO_CONTEXT_AVAILABILITY",
        ],
        "ticker_target_inferred": False,
        "action_direction": False,
        "operational_action_ratio": 0.0,
    }
    assert state["ai_evidence_review"] == {
        "schema_version": "HERD_AI_EVIDENCE_REVIEW_V2",
        "status": "RESEARCH_ONLY_DISABLED_BY_DEFAULT",
        "scope": "LONG_TERM_REVIEW_EVIDENCE_ONLY",
        "lenses": [
            "BUSINESS_HEALTH",
            "EXPECTATION_VALUATION",
            "MARKET_SECTOR",
            "CHART_CROWD",
            "INFORMATION_CHANGE",
            "RED_TEAM",
        ],
        "area_isolation": True,
        "portfolio_data_sent": False,
        "creates_evidence": False,
        "direction_prediction": False,
        "operational_action_ratio": 0.0,
    }
    assert state["operating_review_ledger"] == {
        "schema_version": "HERD_OPERATING_REVIEW_LEDGER_V1",
        "status": "ACTIVE_APPEND_ONLY",
        "ledger_hash_version": "OPERATING_REVIEW_LEDGER_V1",
        "integrity_statuses": [
            "VERIFIED",
            "LEGACY_UNVERIFIED",
            "MISMATCH",
        ],
        "mismatch_outcome_attribution": False,
        "legacy_backfilled": False,
        "creates_direction_evidence": False,
        "operational_action_ratio": 0.0,
    }
    assert state["research_boundary"]["sec_identity_work_unlocks_action_direction"] is False
    assert (
        state["research_boundary"]["next_stage"]
        == "SYNTHESIZE_FAILED_HYPOTHESES_BEFORE_NEW_DIRECTION_RESEARCH"
    )
    hypothesis = state["new_action_hypothesis"]
    assert hypothesis["status"] == "HISTORICAL_FALSIFICATION_FAILED"
    assert hypothesis["historical_screen"] == {
        "passed": False,
        "mature_events": 22,
        "distinct_tickers": 16,
        "calendar_years": 6,
    }
    assert hypothesis["prospective_status"] == "PROSPECTIVE_COLLECTION_ONLY_CONFIRMATION_BLOCKED"
    assert hypothesis["sec_collection_active"] is True
    assert hypothesis["prospective_outcomes_open"] is False
    assert state["new_action_hypothesis"]["direction_evidence_admitted"] is False
    assert state["independent_expansion"] == {
        "status": "SEC_HISTORY_READY",
        "eligible_tickers": 21,
        "sec_covered_tickers": 21,
        "sec_events": 2070,
        "first_acceptance": "2012-01-11T16:29:53Z",
        "last_acceptance": "2026-07-31T20:12:04Z",
        "identity_corrections": 2,
        "historical_reaction_outcomes_opened": True,
        "oos_status": "INDEPENDENT_HISTORICAL_OOS_FAILED",
        "mature_events": 15,
        "distinct_tickers": 9,
        "median_terminal_wealth_delta": -0.10662074675472155,
        "prospective_confirmation_allowed": False,
    }
    assert state["contradictions"] == []
