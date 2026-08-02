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
    assert state["contradictions"] == []
