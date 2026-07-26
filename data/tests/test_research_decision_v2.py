import copy
import json

import pytest

from herd.research_decision_v2 import (
    CATALOG_PATH,
    DECISION_PATH,
    ResearchDecisionError,
    validate_decision,
)


def _inputs():
    return json.loads(DECISION_PATH.read_text()), json.loads(CATALOG_PATH.read_text())


def test_current_decision_is_fail_closed_and_points_to_opportunity_ceiling():
    decision, catalog = _inputs()
    result = validate_decision(decision, catalog)
    assert result["product_scope"] == "STATE_AND_TRANSITION_OBSERVATION"
    assert result["rejected_candidates"] == 4
    assert result["adoptable_action_candidates"] == 0
    assert result["next_stage"] == "PROFIT_TAKE_OPPORTUNITY_CEILING_V1"
    assert result["operational_action_ratio"] == 0.0


def test_rejects_action_authority_without_candidate():
    decision, catalog = _inputs()
    changed = copy.deepcopy(decision)
    changed["product_scope"]["operational_action_ratio"] = 0.05
    with pytest.raises(ResearchDecisionError, match="unsupported model authority"):
        validate_decision(changed, catalog)


def test_rejects_candidate_report_left_in_active_chain():
    decision, catalog = _inputs()
    changed = copy.deepcopy(catalog)
    report = decision["candidate_decisions"][0]["report"]
    changed["chains"]["ACTIVE"].append(report)
    with pytest.raises(ResearchDecisionError, match="remains active"):
        validate_decision(decision, changed)
