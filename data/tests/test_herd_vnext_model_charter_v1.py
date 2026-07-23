import copy

import pytest

from herd.herd_vnext_model_charter_v1 import (
    ModelCharterError,
    load_and_validate,
    validate_charter,
)


def test_vnext_charter_separates_state_action_and_personal_policy():
    charter, report = load_and_validate()

    assert report["status"] == "VNEXT_CHARTER_VERIFIED"
    assert report["default_action"] == "HOLD"
    assert report["operational_action_authority"] == "PROMOTION_GATE"
    assert report["operational_action_ratio"] == 0.0
    assert charter["legacy_boundary"]["HERD_v6.1"] \
        == "LEGACY_RESEARCH_ACTION_BASELINE"


def test_vnext_charter_rejects_personal_inputs_inside_herd_state():
    charter, _ = load_and_validate()
    changed = copy.deepcopy(charter)
    changed["model_layers"][0]["personal_portfolio_input_allowed"] = True

    with pytest.raises(ModelCharterError, match="personal inputs"):
        validate_charter(changed, _sparse_action())


def test_vnext_charter_rejects_unapproved_action_ratio():
    charter, _ = load_and_validate()
    changed = copy.deepcopy(charter)
    changed["output_contract"]["action"]["unapproved_ratio"] = 0.05

    with pytest.raises(ModelCharterError, match="fail closed"):
        validate_charter(changed, _sparse_action())


def _sparse_action():
    import json
    from herd.herd_vnext_model_charter_v1 import SPARSE_ACTION_PATH

    return json.loads(SPARSE_ACTION_PATH.read_text(encoding="utf-8"))
