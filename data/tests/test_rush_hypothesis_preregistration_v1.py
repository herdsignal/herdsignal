from herd.rush_hypothesis_preregistration_v1 import validate_registry


def test_no_failed_or_lead_feature_enters_preregistration():
    report = validate_registry()
    assert report["status"] == "NO_HYPOTHESIS_PREREGISTERED"
    assert report["admitted_hypotheses"] == []
    assert report["confirmation_oos_allowed"] is False
    assert report["operational_action_ratio"] == 0.0
