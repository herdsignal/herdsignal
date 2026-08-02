import copy
import json

import pytest

from herd.research_decision_v5 import (
    CATALOG_PATH,
    DECISION_PATH,
    ResearchDecisionV5Error,
    validate_decision,
)


def _inputs():
    return (
        json.loads(DECISION_PATH.read_text(encoding="utf-8")),
        json.loads(CATALOG_PATH.read_text(encoding="utf-8")),
    )


def test_v5_separates_all_experiments_from_promotion_rounds():
    decision, catalog = _inputs()
    result = validate_decision(decision, catalog)
    assert result["total_locked_rejected_experiments"] == 11
    assert result["promotion_candidate_rounds"] == 6
    assert result["adoptable_action_candidates"] == 0
    assert result["operational_action"] == "HOLD"
    assert result["operational_action_ratio"] == 0.0


def test_v5_rejects_relabeling_latest_failure_as_promotable():
    decision, catalog = _inputs()
    changed = copy.deepcopy(decision)
    changed["latest_hypothesis"]["prospective_confirmation_allowed"] = True
    with pytest.raises(ResearchDecisionV5Error, match="unsupported action"):
        validate_decision(changed, catalog)


def test_v5_requires_failure_synthesis_before_new_hypothesis():
    decision, catalog = _inputs()
    changed = copy.deepcopy(decision)
    changed["next_stage"]["id"] = "REGISTER_NEW_HYPOTHESIS"
    with pytest.raises(ResearchDecisionV5Error, match="next research"):
        validate_decision(changed, catalog)
