import json
from pathlib import Path

from herd.expectation_completed_cycle_v1 import build_decision, cycle_uplift


ROOT = Path(__file__).resolve().parents[1]


def test_cycle_math_rewards_lower_reentry_and_charges_costs():
    gross = cycle_uplift(100, 80, 120, 0.05, 0, 0)
    net = cycle_uplift(100, 80, 120, 0.05, 15, 15)
    assert round(gross, 6) == 0.015
    assert 0 < net < gross


def test_current_dependencies_block_fake_completed_cycle():
    protocol = json.loads((ROOT / "herd/expectation_completed_cycle_v1.json").read_text())
    result = build_decision(protocol, {"eligible": False}, {})
    assert result["decision"] == "DEPENDENCY_BLOCKED"
    assert result["evaluated_cycles"] == 0
    assert result["trim_ratio"] == 0.0
    assert result["operational_action_authority"] is False
