from herd.rush_five_percent_cycle_gate_v1 import evaluate_cycle_gate


def test_five_percent_cycle_stays_blocked_without_confirmed_direction():
    report = evaluate_cycle_gate()
    assert report["status"] == "BLOCKED_NO_CONFIRMED_RUSH_DIRECTION_EVIDENCE"
    assert report["initial_profit_take_fraction"] == 0.0
    assert report["maximum_profit_take_fraction"] == 0.15
    assert report["full_exit_allowed"] is False
    assert report["cycle_executed"] is False
    assert report["buy_hold_comparison_executed"] is False
    assert report["operational_action_ratio"] == 0.0
