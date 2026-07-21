from herd.completed_cycle_gate_v3 import evaluate_completed_cycle_gate


def test_cycle_is_blocked_without_both_direction_evidence_types():
    report = evaluate_completed_cycle_gate()

    assert report["status"] == "BLOCKED_MISSING_PROFIT_TAKE_OR_REENTRY_EVIDENCE"
    assert report["constructed_candidate_ready"] is False
    assert report["profit_take_evidence_ready"] is False
    assert report["reentry_evidence_ready"] is False
    assert report["initial_profit_take_fraction"] == 0.0
    assert report["completed_cycle_executed"] is False
    assert report["buy_hold_comparison_executed"] is False
    assert report["cost_stress_executed"] is False
    assert report["blocked_experiment_is_performance_failure"] is False
    assert report["operational_action_ratio"] == 0.0
    assert report["blind_holdout_access"] is False


def test_future_cycle_contract_preserves_long_term_position():
    contract = evaluate_completed_cycle_gate()["execution_contract_if_eligible"]

    assert contract["initial_profit_take_fraction"] == 0.05
    assert contract["maximum_profit_take_fraction"] == 0.15
    assert contract["reentry_limit"] == "UNSPENT_PROCEEDS_FROM_MATCHED_PRIOR_SALE"
    assert contract["stress_one_way_cost_bps"] == [25, 50]
