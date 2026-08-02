import copy
import json

import pytest

from herd.research_decision_v4 import (
    CATALOG_PATH,
    DECISION_PATH,
    ResearchDecisionV4Error,
    validate_decision,
)


def _inputs():
    return (
        json.loads(DECISION_PATH.read_text(encoding="utf-8")),
        json.loads(CATALOG_PATH.read_text(encoding="utf-8")),
    )


def test_v4_preserves_observation_scope_and_blocks_action():
    decision, catalog = _inputs()
    result = validate_decision(decision, catalog)

    assert result["product_scope"] == "STATE_AND_TRANSITION_OBSERVATION"
    assert result["adoptable_action_candidates"] == 0
    assert result["source_coverage_passed"] is True
    assert result["identity_linkage_passed"] is False
    assert result["pending_source_decisions"] == 110
    assert result["operational_action"] == "HOLD"
    assert result["operational_action_ratio"] == 0.0


def test_v4_rejects_source_coverage_as_direction_evidence():
    decision, catalog = _inputs()
    changed = copy.deepcopy(decision)
    changed["new_source_candidate"]["direction_hypothesis_allowed"] = True

    with pytest.raises(ResearchDecisionV4Error, match="misrepresented"):
        validate_decision(changed, catalog)


def test_v4_rejects_action_authority_while_review_is_pending():
    decision, catalog = _inputs()
    changed = copy.deepcopy(decision)
    changed["product_scope"]["operational_action_ratio"] = 0.05

    with pytest.raises(ResearchDecisionV4Error, match="unsupported model authority"):
        validate_decision(changed, catalog)


def test_v4_requires_catalog_to_use_latest_decision():
    decision, catalog = _inputs()
    changed = copy.deepcopy(catalog)
    changed["current_decision"]["canonical_decision"] = (
        "data/herd/research_decision_v3.json"
    )

    with pytest.raises(ResearchDecisionV4Error, match="does not point"):
        validate_decision(decision, changed)
