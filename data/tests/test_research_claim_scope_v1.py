import copy
import json

import pytest

from herd.research_claim_scope_v1 import (
    CONTRACT_PATH,
    REPORT_PATH,
    ResearchClaimScopeError,
    validate_scope,
)


def _contract():
    return json.loads(CONTRACT_PATH.read_text())


def test_claim_lanes_keep_current_research_but_block_general_action():
    result = validate_scope(_contract())
    assert result["current_holding_research"] == "PREHOLDOUT_ALLOWED_WITH_DISCLOSURE"
    assert result["market_general_model"] == "BLOCKED_SURVIVORSHIP_UNSAFE"
    assert result["next_stage"] == "SIMPLE_ACTION_BASELINES_V1"
    assert result["operational_action_ratio"] == 0.0


def test_personal_shadow_cannot_train_or_auto_authorize():
    changed = copy.deepcopy(_contract())
    changed["lanes"]["PERSONAL_PROSPECTIVE_SHADOW"][
        "may_auto_authorize_user_action"
    ] = True
    with pytest.raises(ResearchClaimScopeError):
        validate_scope(changed)


def test_survivorship_requirement_cannot_be_removed():
    changed = copy.deepcopy(_contract())
    changed["shared_operational_gate"]["survivorship_safe_required"] = False
    with pytest.raises(ResearchClaimScopeError):
        validate_scope(changed)


def test_checked_in_scope_keeps_operational_actions_closed():
    report = json.loads(REPORT_PATH.read_text())
    assert report["status"] == "CLAIM_LANES_SEPARATED"
    assert report["market_general_model"] == "BLOCKED_SURVIVORSHIP_UNSAFE"
    assert report["operational_action_ratio"] == 0.0
