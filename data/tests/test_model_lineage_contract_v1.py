from herd.model_lineage_contract_v1 import validate_contract


def test_model_roles_match_current_sources_and_fail_closed():
    report = validate_contract()
    assert report["status"] == "MODEL_ROLES_VERIFIED"
    assert report["operational_state_model"] == "HERD_V4_STATE"
    assert report["research_action_model"] == "HERD_V61_ACTION_LAYER"
    assert report["research_sample_selector"] == "PRICE_RUSH_EPISODE_V2"
    assert report["operational_action_ratio"] == 0.0
