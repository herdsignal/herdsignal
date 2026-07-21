import copy

import pytest

from herd.action_direction_hypotheses import (
    ActionDirectionRegistryError,
    load_registry,
    validate_registry,
)


def test_registry_separates_all_actions_and_keeps_them_off_operational_path():
    registry, audit = load_registry()
    assert audit["actions"] == ["ADD_BUY", "NEW_ENTRY", "PROFIT_TAKE", "REENTRY"]
    assert audit["operational_authorization"] is False
    assert all(row["parameters_locked"] for row in registry["hypotheses"])


def test_reentry_cannot_be_unblocked_before_profit_evidence():
    registry, _ = load_registry()
    changed = copy.deepcopy(registry)
    reentry = next(row for row in changed["hypotheses"] if row["action"] == "REENTRY")
    reentry["stage"] = "STANDALONE"
    with pytest.raises(ActionDirectionRegistryError, match="reentry"):
        validate_registry(changed)


def test_blind_or_operational_access_cannot_be_enabled():
    registry, _ = load_registry()
    changed = copy.deepcopy(registry)
    changed["blind_holdout_access"] = True
    with pytest.raises(ActionDirectionRegistryError, match="safely locked"):
        validate_registry(changed)
