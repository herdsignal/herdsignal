import json
from pathlib import Path

from herd.sec_guidance_atomic_census_v2_review import adjudicate


ROOT = Path(__file__).resolve().parents[2]


def test_atomic_census_source_review_is_complete_and_price_blind() -> None:
    config = json.loads(
        (ROOT / "data/herd/sec_guidance_atomic_census_v2_review.json").read_text()
    )
    reviewed, report = adjudicate(config)

    assert len(reviewed) == 159
    assert reviewed["review_decision"].ne("PENDING").all()
    assert reviewed["source_integrity_passed"].all()
    assert report["valid_rows"] == 143
    assert report["invalid_rows"] == 3
    assert report["ambiguous_rows"] == 13
    assert report["price_outcomes_observed"] is False
    assert report["blind_holdout_access"] is False
    assert report["operational_action_authority"] is False


def test_atomic_census_source_review_passes_locked_precision_gate() -> None:
    config = json.loads(
        (ROOT / "data/herd/sec_guidance_atomic_census_v2_review.json").read_text()
    )
    _, report = adjudicate(config)

    assert report["source_review_gate_passed"] is True
    assert report["wilson_95_lower_bound"] >= config["minimum_wilson_95_lower_bound"]
    assert report["next_decision"] == "BUILD_SOURCE_REVIEWED_ATOMIC_BINDINGS_V2"
