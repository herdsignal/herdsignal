import copy
import json

import pytest

from herd.model_establishment_status_v1 import (
    ModelEstablishmentStatusError,
    STATUS_PATH,
    validate_status,
)


def test_all_nine_model_establishment_stages_are_hash_verified():
    audit = validate_status(json.loads(STATUS_PATH.read_text()))
    assert audit["stages_verified"] == 9
    assert audit["direction_evidence_admitted"] == 0
    assert audit["blind_holdout_evaluations"] == 0
    assert audit["operational_action_ratio"] == 0.0


def test_integrated_status_cannot_claim_an_action_candidate():
    status = json.loads(STATUS_PATH.read_text())
    changed = copy.deepcopy(status)
    changed["facts"]["direction_evidence_admitted"] = 1
    with pytest.raises(ModelEstablishmentStatusError, match="authority"):
        validate_status(changed)
