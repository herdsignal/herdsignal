from pathlib import Path

from herd.model_downstream_gate_v1 import load_downstream_gate


def test_candidate_is_blocked_before_completed_cycle():
    _, audit = load_downstream_gate(
        Path("data/herd/model_candidate_promotion_gate_v1.json")
    )
    assert audit["stage_id"] == 8
    assert audit["candidate_promoted"] is False
    assert audit["blind_holdout_access"] is False
