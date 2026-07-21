from herd.completed_cycle_gate_v4 import evaluate_completed_cycle_gate


def test_cycle_is_blocked_without_candidate_profit_take_reentry_and_pit():
    report = evaluate_completed_cycle_gate()
    assert report["status"] == "BLOCKED_INCOMPLETE_DIRECTION_OR_PIT_EVIDENCE"
    assert set(report["blocked_reasons"]) == {
        "constructed_candidate", "profit_take_direction", "reentry_direction", "sec_pit_business_state"
    }
    assert report["profit_take_fraction"] == 0.0
    assert report["reentry_fraction"] == 0.0
    assert report["completed_cycle_executed"] is False
    assert report["operational_action_ratio"] == 0.0


def test_reentry_and_pit_alone_cannot_bypass_missing_sell_candidate():
    report = evaluate_completed_cycle_gate(
        reentry_direction_features=["EXAMPLE_REENTRY"], sec_pit_ready=True
    )
    assert report["checks"]["reentry_direction"] is True
    assert report["checks"]["sec_pit_business_state"] is True
    assert report["profit_take_fraction"] == 0.0
    assert report["status"].startswith("BLOCKED")
