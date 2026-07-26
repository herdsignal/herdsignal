import copy
import json

import pytest

from herd.finra_conditional_reentry_gate_v1 import (
    GATE_PATH,
    FinraConditionalReentryGateError,
    validate_gate,
)


def test_reentry_is_blocked_without_validated_trim_cash():
    result = validate_gate(json.loads(GATE_PATH.read_text()))
    assert result["eligible_cash_events"] == 0
    assert result["reentry_simulation_executed"] is False
    assert result["reentry_rows"] == 0
    assert result["operational_action_ratio"] == 0.0


def test_fabricated_reentry_is_rejected():
    gate = json.loads(GATE_PATH.read_text())
    changed = copy.deepcopy(gate)
    changed["decision"]["reentry_rows"] = 1
    with pytest.raises(FinraConditionalReentryGateError, match="fabricated"):
        validate_gate(changed)
