from herd.completed_cycle_gate_v6 import build_report


def test_cycle_waits_for_both_directional_legs(tmp_path):
    report = build_report(tmp_path / "report.json")
    assert report["checks"]["simple_baselines"] is True
    assert report["checks"]["cashflow_contract"] is True
    assert report["checks"]["profit_take_direction"] is False
    assert report["checks"]["conditional_reentry"] is False
    assert report["completed_cycle_executed"] is False
    assert report["operational_action_ratio"] == 0.0
