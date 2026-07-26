import copy
import json
from pathlib import Path

import pytest

from herd.model_downstream_gate_v1 import (
    ModelDownstreamGateError,
    load_downstream_gate,
    validate_downstream_gate,
)


PATH = Path("data/herd/model_sparse_profit_take_gate_v1.json")


def test_sparse_profit_take_fails_closed_without_direction_evidence():
    _, audit = load_downstream_gate(PATH)
    assert audit["stage_id"] == 5
    assert audit["actual"] == 0
    assert audit["trades_simulated"] is False
    assert audit["operational_action_ratio"] == 0.0


def test_blocked_profit_take_cannot_simulate_trades():
    gate = json.loads(PATH.read_text())
    changed = copy.deepcopy(gate)
    changed["execution"]["trades_simulated"] = True
    with pytest.raises(ModelDownstreamGateError, match="executed"):
        validate_downstream_gate(changed)
