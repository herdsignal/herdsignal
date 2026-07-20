import copy

import pytest

from herd.entry_add_buy_policy import (
    EntryAddBuyPolicyError,
    load_policy,
    validate_policy,
)


def test_current_policy_blocks_entry_and_add_buy():
    _, audit = load_policy()

    assert audit["new_entry_authorized"] is False
    assert audit["add_buy_authorized"] is False
    assert audit["company_type_routes"] == 5


def test_policy_cannot_self_authorize_generic_business_guard():
    policy, _ = load_policy()
    changed = copy.deepcopy(policy)
    changed["current_authorization"]["generic_business_guard"] = True

    with pytest.raises(EntryAddBuyPolicyError, match="business evidence"):
        validate_policy(changed)
