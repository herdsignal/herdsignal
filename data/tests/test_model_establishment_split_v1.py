import copy

import pytest

from herd.model_establishment_split_v1 import (
    ModelEstablishmentSplitError,
    load_split,
    validate_split,
)


def test_historical_oos_and_forward_shadow_are_separated():
    _, audit = load_split()
    assert audit["lanes"]["PRICE_TIMING_6M"]["folds"] == 9
    assert audit["lanes"]["PRICE_TIMING_6M"]["oos_years"] >= 5
    assert audit["lanes"]["BUSINESS_STATE_12M"]["folds"] == 4
    assert audit["blind_holdout"] == "SEALED_UNASSIGNED"
    assert audit["prospective_shadow"] == "FORWARD_OBSERVATION_ONLY"
    assert audit["survivorship_safe"] is False


def test_blind_holdout_cannot_receive_a_path_or_date():
    split, _ = load_split()
    changed = copy.deepcopy(split)
    changed["blind_holdout"]["assignment"] = {"start": "2026-01-01"}
    with pytest.raises(ModelEstablishmentSplitError, match="assigned or opened"):
        validate_split(changed)


def test_shadow_cannot_select_a_candidate():
    split, _ = load_split()
    changed = copy.deepcopy(split)
    changed["prospective_shadow"]["may_train_or_select_candidate"] = True
    with pytest.raises(ModelEstablishmentSplitError, match="shadow boundary"):
        validate_split(changed)
