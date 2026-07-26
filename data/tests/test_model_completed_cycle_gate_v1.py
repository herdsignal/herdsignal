from pathlib import Path

from herd.model_downstream_gate_v1 import load_downstream_gate


def test_completed_cycle_is_not_fabricated_from_blocked_legs():
    _, audit = load_downstream_gate(Path("data/herd/model_completed_cycle_gate_v1.json"))
    assert audit["stage_id"] == 7
    assert audit["actual"] is False
    assert audit["trades_simulated"] is False
    assert audit["candidate_promoted"] is False
