from herd.conditional_reentry_gate_v2 import build_report


def test_reentry_stays_blocked_without_validated_sale_cash(tmp_path):
    report = build_report(tmp_path / "report.json")
    assert report["checks"]["validated_profit_take_cash"] is False
    assert report["eligible_cash_events"] == 0
    assert report["reentry_simulation_executed"] is False
    assert report["operational_action_ratio"] == 0.0
