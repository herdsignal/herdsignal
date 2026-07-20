import copy

import pytest

from herd.cycle_action_policy import (
    CycleActionPolicyError,
    load_policy,
    validate_policy,
)


def test_current_cycle_actions_are_not_authorized():
    _, audit = load_policy()

    assert audit["profit_take_authorized"] is False
    assert audit["reentry_authorized"] is False
    assert audit["maximum_fraction"] == 0.15


def test_policy_cannot_authorize_profit_take_without_direction_evidence():
    policy, _ = load_policy()
    changed = copy.deepcopy(policy)
    changed["current_authorization"]["profit_take"] = True

    with pytest.raises(CycleActionPolicyError, match="direction evidence"):
        validate_policy(changed)
