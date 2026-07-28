from herd.personal_action_review_gate_v2 import build_report


def test_personal_mvp_remains_observation_only(tmp_path):
    report = build_report(tmp_path / "report.json")
    assert report["state_observation_ready"] is True
    assert report["action_candidate_ready"] is False
    assert report["default_action"] == "HOLD"
    assert report["operational_action_ratio"] == 0.0
    assert "PROFIT_TAKE_RATIO" in report["blocked_scope"]
