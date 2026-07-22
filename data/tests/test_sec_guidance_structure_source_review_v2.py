import json
from pathlib import Path

from herd.sec_guidance_block_source_review_v1 import adjudicate


ROOT = Path(__file__).resolve().parents[2]


def test_fresh_v2_review_is_complete_and_fails_closed() -> None:
    config = json.loads((ROOT / "data/herd/sec_guidance_structure_review_v2.json").read_text())
    protocol = json.loads((ROOT / "data/herd/sec_guidance_structure_parser_v2.json").read_text())
    reviewed, report = adjudicate(
        ROOT / config["review_template"], ROOT / config["labels"], config, protocol,
    )

    assert len(reviewed) == 80
    assert report["review_complete"] is True
    assert report["review_gate_passed"] is False
    assert report["ready_to_build_revision_pairs"] is False
    assert report["price_outcomes_observed"] is False


def test_known_structural_failures_remain_rejected() -> None:
    config = json.loads((ROOT / "data/herd/sec_guidance_structure_review_v2.json").read_text())
    protocol = json.loads((ROOT / "data/herd/sec_guidance_structure_parser_v2.json").read_text())
    reviewed, _ = adjudicate(
        ROOT / config["review_template"], ROOT / config["labels"], config, protocol,
    )
    decisions = reviewed.set_index("review_id")["review_decision"]
    for review_id in ("SG2-0022", "SG2-0059", "SG2-0072"):
        assert decisions[review_id] == "INVALID"
