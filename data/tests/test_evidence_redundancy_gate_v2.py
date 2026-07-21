from herd.evidence_redundancy_gate_v2 import evaluate_redundancy_gate


def test_failed_candidates_cannot_enter_redundancy_audit():
    report = evaluate_redundancy_gate()

    assert report["status"] == "BLOCKED_NO_INDEPENDENT_OOS_EVIDENCE"
    assert report["admitted_direction_features"] == []
    assert report["correlation_audit_executed"] is False
    assert report["conditional_effect_audit_executed"] is False
    assert report["ablation_executed"] is False
    assert report["weights_allowed"] is False
    assert report["operational_action_ratio"] == 0.0
    assert report["blind_holdout_access"] is False
