from herd.opportunity_cycle_gate_v3 import evaluate_cycle_gate, load_v3_registry


def test_v3_registry_matches_oos_and_blocks_cycle():
    _, audit = load_v3_registry()
    result = evaluate_cycle_gate()
    assert audit["pullback_evidence"] == 0
    assert result["initial_profit_take_fraction"] == 0.0
    assert result["five_percent_cycle_executed"] is False
    assert result["buy_hold_comparison_executed"] is False
    assert result["blocked_experiment_is_performance_failure"] is False
    assert result["operational_action_ratio"] == 0.0
