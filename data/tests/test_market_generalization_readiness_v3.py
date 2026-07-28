from herd.market_generalization_readiness_v3 import build_report


def test_market_claim_stays_blocked_with_explicit_public_data_gaps(tmp_path):
    report = build_report(tmp_path / "report.json")
    assert report["allowed_claim"] == "CURRENT_CONSTITUENT_PERSONAL_DIAGNOSTIC"
    assert report["event_replay"]["unresolved"] == 16
    assert report["coverage"]["historical_price_fraction"] < 0.95
    assert report["coverage"]["delisted_price_fraction"] < 0.95
    assert report["survivorship_safe"] is False
    assert report["operational_action_ratio"] == 0.0
