import copy
import json

import pytest

from herd.sec_form4_nonroutine_sale_rush_preregistration_v1 import (
    PROTOCOL_PATH,
    Form4SaleRushPreregistrationError,
    validate_preregistration,
)


def _protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def test_locked_protocol_and_inputs_are_valid():
    result = validate_preregistration(_protocol())
    assert result["lookback_calendar_days"] == 30
    assert result["minimum_distinct_reporting_owners"] == 2
    assert result["outcome_peeking"] is False
    assert result["operational_action_ratio"] == 0.0


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("exposure", "lookback_calendar_days", 60),
        ("exposure", "minimum_distinct_reporting_owners", 1),
        ("adoption_gate", "minimum_pooled_relative_risk", 1.0),
        ("decision_boundary", "historical_pass_can_authorize_action", True),
        ("decision_boundary", "operational_action_ratio", 0.05),
    ],
)
def test_rejects_post_result_boundary_changes(section, key, value):
    changed = copy.deepcopy(_protocol())
    changed[section][key] = value
    with pytest.raises(Form4SaleRushPreregistrationError):
        validate_preregistration(changed)
