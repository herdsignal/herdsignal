from herd.completed_cycle_gate_v2 import evaluate_completed_cycle_gate


def test_cycle_is_not_run_when_independent_evidence_failed():
    result = evaluate_completed_cycle_gate()
    assert result["status"] == "BLOCKED_MISSING_INDEPENDENT_EVIDENCE"
    assert result["completed_cycle_evaluation_executed"] is False
    assert result["completed_cycle_allowed"] is False
    assert result["initial_profit_take_fraction"] == 0.0
    assert result["operational_action_ratio"] == 0.0
