import json
from pathlib import Path

from herd.model_downstream_gate_v1 import load_downstream_gate


PATH = Path("data/herd/model_prospective_shadow_gate_v1.json")


def test_state_observation_continues_but_action_shadow_is_blocked():
    gate, audit = load_downstream_gate(PATH)
    assert audit["stage_id"] == 9
    assert gate["execution"]["state_observation_continues"] is True
    assert gate["execution"]["action_candidate_shadow_enabled"] is False
    assert audit["operational_action_ratio"] == 0.0


def test_blind_holdout_remains_unopened():
    gate = json.loads(PATH.read_text())
    assert gate["authority"]["blind_holdout_access"] is False
