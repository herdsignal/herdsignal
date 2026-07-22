import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_research_gate_v4 import build_gate_state


ROOT = Path(__file__).resolve().parents[2]


def test_v4_review_is_complete_but_fails_locked_precision_gate() -> None:
    review = json.loads((ROOT / "data/reports/sec_guidance_structure_v4_source_review.json").read_text())
    assert review["reviewed_rows"] == 80
    assert review["distinct_tickers"] == 23
    assert review["source_precision"] == 0.8
    assert review["wilson_95_lower_bound"] < 0.9
    assert review["review_gate_passed"] is False
    assert review["price_outcomes_observed"] is False


def test_v4_failure_blocks_research_steps_three_through_eight() -> None:
    protocol = json.loads((ROOT / "data/herd/sec_guidance_research_gate_v4.json").read_text())
    review = json.loads((ROOT / protocol["source_review_report"]).read_text())
    labels = pd.read_csv(ROOT / protocol["source_review_labels"])
    report = build_gate_state(protocol, review, labels)
    assert report["decision"] == "PARSER_V5_REQUIRED"
    assert report["steps"][1]["status"] == "FAILED"
    assert all(step["status"] == "BLOCKED" for step in report["steps"][2:])
    assert sum(report["failure_taxonomy"].values()) == 16
    assert report["operational_action_ratio"] == 0
