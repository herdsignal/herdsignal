import copy
import json

import pytest

from herd.finra_five_percent_trim_gate_v1 import (
    GATE_PATH,
    FinraFivePercentTrimGateError,
    validate_gate,
)


def test_failed_direction_evidence_creates_no_trades():
    result = validate_gate(json.loads(GATE_PATH.read_text()))
    assert result["simulation_executed"] is False
    assert result["trade_rows"] == 0
    assert result["buy_and_hold_comparison_executed"] is False
    assert result["operational_action_ratio"] == 0.0


def test_trade_execution_after_failed_direction_is_rejected():
    gate = json.loads(GATE_PATH.read_text())
    changed = copy.deepcopy(gate)
    changed["decision"]["simulation_executed"] = True
    with pytest.raises(FinraFivePercentTrimGateError, match="trading"):
        validate_gate(changed)
