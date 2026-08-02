import copy
import json

import pytest

from herd.research_decision_v3 import (
    CATALOG_PATH,
    DECISION_PATH,
    ResearchDecisionV3Error,
    validate_decision,
)


def _inputs():
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    catalog["current_decision"]["canonical_decision"] = (
        "data/herd/research_decision_v3.json"
    )
    return json.loads(DECISION_PATH.read_text(encoding="utf-8")), catalog


def test_v3_reproduces_its_historical_latest_rejection():
    decision, catalog = _inputs()
    result = validate_decision(decision, catalog)

    assert result["product_scope"] == "STATE_AND_TRANSITION_OBSERVATION"
    assert result["evaluated_candidates"] == 5
    assert result["adoptable_action_candidates"] == 0
    assert result["latest_candidate_decision"] == "REJECTED_PREHOLDOUT_OOS"
    assert result["next_stage"] == "DISTINCT_PUBLIC_PIT_INFORMATION_FEASIBILITY_V1"
    assert result["operational_action"] == "HOLD"
    assert result["operational_action_ratio"] == 0.0


def test_v3_rejects_action_authority_without_evidence():
    decision, catalog = _inputs()
    changed = copy.deepcopy(decision)
    changed["product_scope"]["operational_action_ratio"] = 0.05

    with pytest.raises(ResearchDecisionV3Error, match="unsupported model authority"):
        validate_decision(changed, catalog)


def test_v3_rejects_rewriting_latest_failure_as_a_pass():
    decision, catalog = _inputs()
    changed = copy.deepcopy(decision)
    changed["latest_candidate"]["all_adoption_gates_passed"] = True

    with pytest.raises(ResearchDecisionV3Error, match="misrepresented"):
        validate_decision(changed, catalog)


def test_v3_requires_catalog_to_use_the_latest_canonical_decision():
    decision, catalog = _inputs()
    changed = copy.deepcopy(catalog)
    changed["current_decision"]["canonical_decision"] = (
        "data/herd/research_decision_v2.json"
    )

    with pytest.raises(ResearchDecisionV3Error, match="does not point"):
        validate_decision(decision, changed)
