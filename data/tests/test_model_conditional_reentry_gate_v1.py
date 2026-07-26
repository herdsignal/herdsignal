from pathlib import Path

from herd.model_downstream_gate_v1 import load_downstream_gate


def test_reentry_is_blocked_without_verified_sale_proceeds():
    _, audit = load_downstream_gate(
        Path("data/herd/model_conditional_reentry_gate_v1.json")
    )
    assert audit["stage_id"] == 6
    assert audit["blocker"] == "verified_profit_take_proceeds_exist"
    assert audit["actual"] is False
    assert audit["trades_simulated"] is False
