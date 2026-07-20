import copy

import pytest

from herd.evidence_admission import (
    EvidenceAdmissionError,
    load_registry,
    validate_registry,
)


def test_current_oos_evidence_does_not_authorize_direction_or_cycles():
    _, audit = load_registry()

    assert audit["direction_family_count"] == 0
    assert all(count == 0 for count in audit["action_authorizations"].values())
    assert audit["cap_ablation_families"] == ["MARKET_RISK"]
    assert audit["herd_next_composition_allowed"] is False
    assert audit["operational_action_ratio"] == 0.0


def test_downside_risk_cannot_be_changed_into_direction_signal():
    registry, _ = load_registry()
    changed = copy.deepcopy(registry)
    market_risk = next(
        family for family in changed["families"] if family["id"] == "MARKET_RISK"
    )
    market_risk["direction_authorized"] = True

    with pytest.raises(EvidenceAdmissionError, match="validated role"):
        validate_registry(changed)


def test_rejected_rush_cannot_authorize_profit_take():
    registry, _ = load_registry()
    changed = copy.deepcopy(registry)
    changed["composite_hypotheses"][0]["profit_take_authorized"] = True

    with pytest.raises(EvidenceAdmissionError, match="Rush"):
        validate_registry(changed)
