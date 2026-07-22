import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_research_gate_v3 import build_gate_state


ROOT = Path(__file__).resolve().parents[2]


def test_failed_v3_precision_blocks_research_steps_three_through_eight() -> None:
    protocol = json.loads((ROOT / "data/herd/sec_guidance_research_gate_v3.json").read_text())
    review = json.loads((ROOT / protocol["source_review_report"]).read_text())
    labels = pd.read_csv(ROOT / protocol["source_review_labels"])
    report = build_gate_state(protocol, review, labels)

    assert report["steps"][0]["status"] == "COMPLETE"
    assert report["steps"][1]["status"] == "FAILED"
    assert all(step["status"] == "BLOCKED" for step in report["steps"][2:])
    assert report["decision"] == "PARSER_V4_REQUIRED"
    assert report["operational_action_ratio"] == 0
    assert report["price_outcomes_observed"] is False


def test_failure_taxonomy_preserves_v4_work_items() -> None:
    protocol = json.loads((ROOT / "data/herd/sec_guidance_research_gate_v3.json").read_text())
    review = json.loads((ROOT / protocol["source_review_report"]).read_text())
    labels = pd.read_csv(ROOT / protocol["source_review_labels"])
    report = build_gate_state(protocol, review, labels)

    assert sum(report["failure_taxonomy"].values()) == 26
    assert report["failure_taxonomy"]["QUARTER_RANGE_MAPPED_TO_FULL_YEAR"] == 4
    assert "PRESERVE_TABLE_ROW_COLUMN_AND_HEADER_HIERARCHY" in report["next_parser_requirements"]
