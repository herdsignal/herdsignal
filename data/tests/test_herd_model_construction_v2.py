from herd.herd_model_construction_v2 import evaluate_construction


def test_model_is_not_constructed_without_admitted_direction_evidence():
    report = evaluate_construction()

    assert report["status"] == "NO_CANDIDATE_CONSTRUCTED"
    assert report["candidate_families_planned"] == ["B0", "B1", "B2", "B3", "B4", "B5"]
    assert report["candidate_families_constructed"] == []
    assert report["candidate_count"] == 0
    assert report["reentry_direction_ready"] is False
    assert report["weights"] == {}
    assert report["model_promotion_allowed"] is False
    assert report["operational_action_ratio"] == 0.0
    assert report["blind_holdout_access"] is False
