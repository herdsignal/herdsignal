import copy
import json

import pytest

from herd.finra_completed_cycle_gate_v1 import (
    GATE_PATH,
    FinraCompletedCycleGateError,
    validate_gate,
)


def test_no_completed_cycle_is_claimed_without_actions():
    result = validate_gate(json.loads(GATE_PATH.read_text()))
    assert result["completed_cycles"] == 0
    assert result["benchmark_comparisons"] == 0
    assert result["candidate_promotable"] is False
    assert result["operational_action_ratio"] == 0.0


def test_incomplete_candidate_cannot_be_promoted():
    gate = json.loads(GATE_PATH.read_text())
    changed = copy.deepcopy(gate)
    changed["decision"]["candidate_promotable"] = True
    with pytest.raises(FinraCompletedCycleGateError, match="promoted"):
        validate_gate(changed)
