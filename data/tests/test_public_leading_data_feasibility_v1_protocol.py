import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "data/herd/public_leading_data_feasibility_v1.json"


def _protocol() -> dict:
    return json.loads(PROTOCOL.read_text(encoding="utf-8"))


def test_protocol_keeps_public_research_and_action_firewalls_locked():
    protocol = _protocol()
    assert protocol["status"] == "LOCKED_BEFORE_LOCAL_FEASIBILITY_AUDIT"
    assert protocol["research_tier"] == "PUBLIC_RESEARCH_ONLY"
    assert protocol["primary_oos_gate"]["all_required"] is True
    assert protocol["authority"]["new_direction_hypothesis_allowed"] is False
    assert protocol["authority"]["operational_action_ratio"] == 0.0
    assert "RETUNE_FORM4_OR_GUIDANCE_ON_THE_SAME_OUTCOMES" in protocol["forbidden"]
    assert "TREAT_FREE_OPTION_VOLUME_AS_IV_OR_SKEW" in protocol["forbidden"]


def test_prior_research_and_public_contract_hashes_are_immutable():
    protocol = _protocol()
    artifacts = [
        *protocol["prior_research"],
        protocol["public_research_contract"],
    ]
    for artifact in artifacts:
        path = ROOT / artifact["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]


def test_source_boundaries_match_official_public_tier_claims():
    sources = {source["id"]: source for source in _protocol()["sources"]}
    assert all(
        url.startswith("https://")
        for source in sources.values()
        for url in source["official_urls"]
    )
    finra = sources["FINRA_EXCHANGE_LISTED_SHORT_INTEREST"]
    assert finra["pit_start"] == "2021-06-01"
    assert finra["publication_lag_class"] == "WITHIN_10_BUSINESS_DAYS"
    form13 = sources["SEC_13F_INSTITUTIONAL_HOLDINGS"]
    assert form13["pit_start"] == "2013-05-01"
    assert form13["publication_lag_class"] == "UP_TO_45_CALENDAR_DAYS"
    option_surface = sources["CBOE_EQUITY_OPTION_SURFACE"]
    assert option_surface["public_research_tier_compatible"] is False
