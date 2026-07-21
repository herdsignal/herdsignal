from herd.herd_candidate_protocol_v2 import load_and_validate


def test_candidate_formulas_are_locked_before_results():
    protocol, report = load_and_validate()
    assert report["locked_before_results"] is True
    assert report["features"] == 11
    assert report["hypotheses"] == 11
    assert report["weights_allowed"] is False
    assert protocol["common"]["primary_horizon_weeks"] == 13


def test_regime_cannot_create_direction_and_actions_remain_disabled():
    protocol, report = load_and_validate()
    assert protocol["adoption_gates"]["REGIME_CONTEXT"]["cannot_pass_as_direction"] is True
    assert report["operational_actions_allowed"] is False
    assert "COMBINE_BEFORE_INDEPENDENT_PASS" in protocol["forbidden"]
