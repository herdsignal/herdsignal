from herd.prospective_readiness_gate_v2 import build_report


def test_state_collection_continues_without_action_shadow(tmp_path):
    report = build_report(tmp_path / "report.json")
    assert report["state_observation_collection"] is True
    assert report["action_candidate_shadow"] is False
    assert report["matured_outcomes"] == 0
    assert report["operational_action_ratio"] == 0.0
