import json

from herd.evidence_admission_v2 import load_evidence_admission_v2


def test_rejected_v2_evidence_cannot_enable_cycle():
    registry, audit = load_evidence_admission_v2()
    assert audit["admitted_profit_take_count"] == 0
    assert audit["completed_cycle_allowed"] is False
    assert audit["operational_action_ratio"] == 0.0
    assert all(not item["authorized"] for item in registry["profit_take_families"])
