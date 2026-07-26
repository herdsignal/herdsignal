import copy

import pytest

from herd.model_evidence_admission_v1 import (
    ModelEvidenceAdmissionError,
    load_registry,
    validate_registry,
)


def test_only_risk_context_is_admitted():
    _, audit = load_registry()
    assert audit["direction_evidence_admitted"] == 0
    assert audit["risk_context_admitted"] == 1
    assert audit["profit_take_gate_passed"] is False
    assert audit["operational_action_ratio"] == 0.0


def test_rejected_price_evidence_cannot_be_promoted():
    registry, _ = load_registry()
    changed = copy.deepcopy(registry)
    changed["families"][0]["admitted"] = True
    with pytest.raises(ModelEvidenceAdmissionError, match="role widened"):
        validate_registry(changed)
