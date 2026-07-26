import copy
import json

import pytest

from herd.model_parts_j_o_promotion_audit_v1 import (
    AUDIT_PATH,
    ModelPartsJOPromotionAuditError,
    validate_audit,
)


def test_parts_j_o_keep_mvp_state_observation_only():
    result = validate_audit(json.loads(AUDIT_PATH.read_text()))
    assert len(result["completed_parts"]) == 6
    assert result["mvp_scope"] == "STATE_AND_TRANSITION_OBSERVATION_ONLY"
    assert result["new_model_name"] == "UNASSIGNED_UNTIL_PROMOTION"
    assert result["blind_holdout_access"] is False
    assert result["operational_action_ratio"] == 0.0


def test_candidate_cannot_be_invented_during_combination():
    audit = json.loads(AUDIT_PATH.read_text())
    changed = copy.deepcopy(audit)
    changed["parts"]["J_COMBINATION"]["candidate_combinations"] = 1
    with pytest.raises(ModelPartsJOPromotionAuditError, match="promoted"):
        validate_audit(changed)
