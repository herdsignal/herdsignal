import copy
import json

import pytest

from herd.finra_rush_divergence_preregistration_v1 import (
    PROTOCOL_PATH,
    FinraRushDivergencePreregistrationError,
    validate_preregistration,
)


def test_one_finra_rush_hypothesis_is_locked_without_action_authority():
    result = validate_preregistration(json.loads(PROTOCOL_PATH.read_text()))
    assert result["hypothesis"] == "FINRA_RUSH_DTC_DIVERGENCE_V1"
    assert result["conditions"] == 3
    assert result["historical_role"] == "RECENT_PREHOLDOUT_SENSITIVITY_ONLY"
    assert result["prospective_confirmation_months"] == 18
    assert result["historical_action_authority"] is False
    assert result["operational_action_ratio"] == 0.0


def test_historical_result_cannot_authorize_action():
    protocol = json.loads(PROTOCOL_PATH.read_text())
    changed = copy.deepcopy(protocol)
    changed["decision_boundary"]["historical_pass_can_authorize_action"] = True
    with pytest.raises(FinraRushDivergencePreregistrationError, match="widened"):
        validate_preregistration(changed)
