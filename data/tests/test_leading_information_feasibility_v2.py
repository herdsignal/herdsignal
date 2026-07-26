import copy
import json

import pytest

from herd.leading_information_feasibility_v2 import (
    PROTOCOL_PATH,
    LeadingInformationFeasibilityV2Error,
    validate_feasibility,
)


def test_public_leading_sources_remain_fail_closed():
    result = validate_feasibility(json.loads(PROTOCOL_PATH.read_text()))
    assert result["form4_independent_issuers"] == 387
    assert result["guidance_valid_rows"] == 700
    assert result["finra_settlement_dates"] == 122
    assert result["primary_long_horizon_source_ready_count"] == 0
    assert result["prospective_shadow_source_count"] == 1
    assert result["operational_action_ratio"] == 0.0


def test_feasibility_cannot_authorize_historical_direction():
    protocol = json.loads(PROTOCOL_PATH.read_text())
    changed = copy.deepcopy(protocol)
    changed["decision"]["new_historical_direction_hypothesis_allowed"] = True
    with pytest.raises(LeadingInformationFeasibilityV2Error, match="authority"):
        validate_feasibility(changed)
