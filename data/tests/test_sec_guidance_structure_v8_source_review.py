import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_block_source_review_v1 import adjudicate


ROOT = Path(__file__).resolve().parents[2]


def test_v8_locked_source_review_fails_without_opening_part_b() -> None:
    config = json.loads((ROOT / "data/herd/sec_guidance_structure_v8_review.json").read_text())
    protocol = json.loads((ROOT / "data/herd/sec_guidance_v8_second_wave_validation.json").read_text())
    reviewed, report = adjudicate(
        ROOT / config["review_template"], ROOT / config["labels"], config, protocol,
    )
    assert len(reviewed) == 80
    assert reviewed["ticker"].nunique() == 20
    assert report["valid_rows"] == 72
    assert report["invalid_rows"] == 8
    assert report["source_precision"] == 0.9
    assert report["wilson_95_lower_bound"] < protocol["review_gate"]["minimum_wilson_95_lower_bound"]
    assert report["review_gate_passed"] is False
    assert report["ready_to_build_revision_pairs"] is False
    assert report["ready_for_direction_preregistration"] is False


def test_v8_failures_cover_all_observed_binding_families() -> None:
    labels = pd.read_csv(ROOT / "data/herd/sec_guidance_structure_v8_review_labels.csv")
    reasons = set(labels.loc[labels["review_decision"].eq("INVALID"), "review_reason"])
    assert "RESPECTIVELY_FIRST_RANGE_ASSIGNED_NON_GAAP" in reasons
    assert "PRIOR_GUIDANCE_RANGE_SELECTED_AS_CURRENT" in reasons
    assert "SHARE_COUNT_MISCLASSIFIED_AS_EPS" in reasons
    assert "NON_GAAP_ROW_MISCLASSIFIED_AS_GAAP" in reasons
    assert "FULL_YEAR_GUIDANCE_MAPPED_TO_REPORTING_QUARTER" in reasons
    assert "PREVIOUSLY_ANNOUNCED_RANGE_SELECTED_AS_CURRENT" in reasons
