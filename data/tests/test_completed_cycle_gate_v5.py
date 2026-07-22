import json
from pathlib import Path

from herd.completed_cycle_gate_v5 import evaluate


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "data/herd/completed_cycle_gate_v5.json").read_text())


def test_completed_cycle_remains_fully_blocked_without_all_evidence() -> None:
    report = evaluate(PROTOCOL)
    assert report["status"] == "BLOCKED_INCOMPLETE_EVIDENCE"
    assert report["blocked_reasons"] == [
        "constructed_candidate", "profit_take_direction", "reentry_direction", "sec_pit_business_veto",
    ]
    assert report["profit_take_fraction"] == 0
    assert report["reentry_fraction"] == 0
    assert report["completed_cycle_executed"] is False
    assert report["buy_hold_comparison_executed"] is False
    assert report["cost_stress_executed"] is False
    assert report["model_promotion_allowed"] is False
    assert report["operational_action_ratio"] == 0
    assert report["blind_holdout_access"] is False
