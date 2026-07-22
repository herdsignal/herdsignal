import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_research_gate_v2 import build_gate_state


ROOT = Path(__file__).resolve().parents[2]


def test_failed_precision_blocks_steps_three_through_eight() -> None:
    protocol = json.loads((ROOT / "data/herd/sec_guidance_research_gate_v2.json").read_text())
    review = json.loads((ROOT / "data/reports/sec_guidance_structure_source_review_v2.json").read_text())
    labels = pd.read_csv(ROOT / "data/herd/sec_guidance_structure_review_labels_v2.csv")
    report = build_gate_state(protocol, review, labels)

    assert report["steps"][0]["status"] == "COMPLETE"
    assert report["steps"][1]["status"] == "FAILED"
    assert all(step["status"] == "BLOCKED" for step in report["steps"][2:])
    assert report["price_outcomes_observed"] is False
    assert report["operational_action_ratio"] == 0


def test_failure_taxonomy_preserves_parser_v3_requirements() -> None:
    protocol = json.loads((ROOT / "data/herd/sec_guidance_research_gate_v2.json").read_text())
    review = json.loads((ROOT / "data/reports/sec_guidance_structure_source_review_v2.json").read_text())
    labels = pd.read_csv(ROOT / "data/herd/sec_guidance_structure_review_labels_v2.csv")
    report = build_gate_state(protocol, review, labels)

    assert report["failure_taxonomy"]["COMPARISON_PERIOD_MAPPED_AS_GUIDANCE_PERIOD"] == 10
    assert report["decision"] == "PARSER_V3_REQUIRED"
