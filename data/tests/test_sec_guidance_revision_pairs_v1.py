import json
from pathlib import Path

from herd.sec_guidance_revision_pairs_v1 import PAIR_COLUMNS, build_pairs


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "data/herd/sec_guidance_revision_pairs_v1.json").read_text())


def test_revision_pair_builder_stops_at_failed_source_precision_gate() -> None:
    pairs, report = build_pairs(PROTOCOL)
    assert list(pairs.columns) == PAIR_COLUMNS
    assert pairs.empty
    assert report["source_precision_gate_passed"] is False
    assert report["pair_build_blocked"] is True
    assert report["source_qualified_pairs"] == 0
    assert report["pair_coverage_gate_passed"] is False
    assert report["direction_labels_created"] is False
    assert report["price_outcomes_observed"] is False
    assert report["operational_action_ratio"] == 0
