from herd.herd_model_construction_v3 import evaluate_construction


def test_no_failed_evidence_is_combined_into_candidate():
    report = evaluate_construction()
    assert report["status"] == "BLOCKED_NO_ADMITTED_DIRECTION_EVIDENCE"
    assert report["admitted_direction_features"] == []
    assert len(report["rejected_direction_features"]) == 4
    assert report["candidate_count"] == 0
    assert report["weights"] == {}
    assert report["existing_v4_preserved"] is True
    assert report["operational_action_ratio"] == 0.0
