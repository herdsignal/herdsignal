import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.decision_architecture_v1 import (
    DecisionArchitectureError,
    load_contract,
    validate_contract,
)


def test_three_layers_are_locked_without_action_authority():
    report = validate_contract(load_contract())

    assert report["layers"] == {
        "state": "OBSERVATION_READY",
        "action_edge": "NO_ADOPTABLE_CANDIDATE",
        "portfolio_policy": "BLOCKED_UNTIL_ACTION_EDGE_ADMISSION",
    }
    assert report["next_stage"] == "FIXED_POLICY_NET_VALUE_TARGET_V1"
    assert report["operational_action"] == "HOLD"
    assert report["operational_action_ratio"] == 0.0
    assert report["blind_holdout_access"] is False


@pytest.mark.parametrize(
    ("section", "field", "value", "message"),
    [
        ("layers", "action_edge", {"model": "UNVERIFIED"}, "three-layer"),
        ("research_design", "maximum_candidates_per_ticker_year", 5, "research design"),
        ("evaluation", "log_loss_is_sole_admission_gate", True, "economic evaluation"),
        ("firewall", "operational_action_ratio", 0.05, "unverified action"),
    ],
)
def test_contract_fails_closed_when_a_boundary_is_weakened(
    section, field, value, message
):
    contract = copy.deepcopy(load_contract())
    if section == "layers":
        contract[section][field].update(value)
    else:
        contract[section][field] = value

    with pytest.raises(DecisionArchitectureError, match=message):
        validate_contract(contract)


def test_legacy_action_runtime_stop_rule_cannot_be_removed():
    contract = copy.deepcopy(load_contract())
    contract["stop"].remove(
        "RUN_LEGACY_V61_ACTION_CALCULATION_ON_OPERATIONAL_STATE_READ"
    )

    with pytest.raises(DecisionArchitectureError, match="stop"):
        validate_contract(contract)
