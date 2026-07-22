import json
from pathlib import Path

from herd.herd_model_construction_v4 import construct


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "data/herd/herd_model_construction_v4.json").read_text())


def test_no_failed_evidence_is_recombined_into_new_herd() -> None:
    report = construct(PROTOCOL)
    assert report["status"] == "BLOCKED_NO_ADMITTED_DIRECTION_EVIDENCE"
    assert report["admitted_direction_evidence"] == []
    assert report["admitted_business_veto"] is False
    assert report["business_veto_used_as_direction"] is False
    assert report["instantiated_candidates"] == []
    assert report["candidate_count"] == 0
    assert report["weights"] == {}
    assert report["existing_v4_preserved"] is True
    assert report["model_promotion_allowed"] is False
    assert report["blind_holdout_access"] is False
    assert report["operational_action_ratio"] == 0
