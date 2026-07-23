import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "data/herd/finra_short_interest_immutable_census_v1.json"


def _protocol() -> dict:
    return json.loads(PROTOCOL.read_text(encoding="utf-8"))


def test_protocol_is_locked_before_collection_and_keeps_action_firewall_closed():
    protocol = _protocol()
    assert protocol["status"] == "LOCKED_BEFORE_COLLECTION"
    assert protocol["research_tier"] == "PUBLIC_RESEARCH_ONLY"
    assert protocol["authority"]["allowed_research_role"] == (
        "RECENT_SENSITIVITY_AND_PROSPECTIVE_SHADOW_ONLY"
    )
    assert protocol["authority"]["primary_long_horizon_oos_allowed"] is False
    assert protocol["authority"]["price_outcomes_opened"] is False
    assert protocol["authority"]["direction_hypothesis_allowed"] is False
    assert protocol["authority"]["operational_action_ratio"] == 0.0


def test_protocol_distinguishes_settlement_publication_and_revision_times():
    policy = _protocol()["point_in_time_policy"]
    assert policy["settlement_date_is_not_publication_date"] is True
    assert policy["official_publication_rule"] == (
        "SEVENTH_FINRA_BUSINESS_DAY_AFTER_SETTLEMENT"
    )
    assert policy["http_last_modified_is_revision_metadata_not_original_publication_time"]


def test_immutable_storage_preserves_revisions_as_new_versions():
    storage = _protocol()["immutable_storage"]
    assert storage["append_only"] is True
    assert storage["overwrite_existing_hash_forbidden"] is True
    assert storage["same_settlement_date_new_hash_is_new_version"] is True
    assert "{sha256}" in storage["raw_layout"]
    assert storage["hash_algorithm"] == "SHA-256"


def test_locked_inputs_and_prerequisite_have_expected_hashes():
    protocol = _protocol()
    artifacts = [
        protocol["prerequisite"],
        *protocol["identifier_policy"]["locked_inputs"],
    ]
    for artifact in artifacts:
        path = ROOT / artifact["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]


def test_current_ticker_backfill_and_outcome_access_are_forbidden():
    protocol = _protocol()
    assert protocol["identifier_policy"]["current_symbol_backfill_forbidden"] is True
    assert "OPEN_PRICE_OR_RETURN_OUTCOMES" in protocol["forbidden"]
    assert "BACKFILL_CURRENT_TICKER_ACROSS_AN_UNVERIFIED_RENAME" in protocol["forbidden"]
