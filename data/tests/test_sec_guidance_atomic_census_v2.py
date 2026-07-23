import hashlib
import json
from pathlib import Path

from herd.sec_guidance_atomic_census_v2 import build


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = ROOT / "data/herd/sec_guidance_atomic_census_v2.json"


def test_atomic_census_locks_only_source_available_pending_candidates() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text())
    review, report = build(protocol)

    assert not review.empty
    assert review["review_id"].is_unique
    assert review["source_available"].all()
    assert review["review_decision"].eq("PENDING").all()
    assert review["reviewer"].eq("").all()
    assert report["all_rows_pending"] is True
    assert report["price_outcomes_observed"] is False
    assert report["direction_hypothesis_preregistered"] is False
    assert report["operational_action_ratio"] == 0.0


def test_atomic_census_has_enough_price_blind_pair_potential() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text())
    _, report = build(protocol)

    assert report["potential_revision_pairs_if_all_valid"] >= (
        protocol["coverage_gate"]["minimum_source_reviewed_revision_pairs"]
    )
    assert report["potential_revision_pair_tickers_if_all_valid"] >= (
        protocol["coverage_gate"]["minimum_distinct_tickers"]
    )
    assert report["status"] == "LOCKED_PENDING_SOURCE_REVIEW"


def test_atomic_census_inputs_are_hash_locked() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text())
    for item in [protocol["existing_atomic_bindings"], *protocol["candidate_sources"]]:
        path = ROOT / item["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
