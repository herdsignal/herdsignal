from pathlib import Path

from tools.current_state_audit import build_current_state


ROOT = Path(__file__).resolve().parents[2]


def test_current_state_contracts_are_consistent() -> None:
    state = build_current_state(ROOT)

    assert state["status"] == "PASS"
    assert state["product"]["state_model"] == "HERD_STATE_S1"
    assert state["action_research"]["adoptable_candidates"] == 0
    assert state["action_research"]["operational_action_ratio"] == 0.0
    assert state["action_research"]["blind_holdout_open"] is False
    assert state["research_boundary"]["sec_identity_work_unlocks_action_direction"] is False
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
        "outcomes_open": False,
    }
    assert state["contradictions"] == []
