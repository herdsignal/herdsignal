from herd.indicator_inventory_v2 import load_and_audit


def test_inventory_v2_covers_operational_and_research_layers():
    registry, report = load_and_audit()
    assert report["inventory_complete"] is True
    assert report["inventory_items"] >= 25
    assert report["layers"]["OPERATIONAL_V4_INPUT"] == 6
    assert report["layers"]["RESEARCH_CANDIDATE"] >= 10
    assert registry["design_rules"]["weights_require_independent_oos_and_redundancy_audit"] is True


def test_research_candidates_cannot_silently_gain_direction_authority():
    _, report = load_and_audit()
    assert report["research_candidates_with_direction_authority"] == []
    assert report["model_components_selected"] is False
    assert report["weights_selected"] is False
