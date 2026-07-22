import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_block_source_review_v1 import adjudicate


ROOT = Path(__file__).resolve().parents[2]


def test_v9_locked_source_review_fails_without_opening_part_b() -> None:
    config = json.loads((ROOT / "data/herd/sec_guidance_structure_v9_review.json").read_text())
    protocol = json.loads((ROOT / "data/herd/sec_guidance_v9_independent_validation.json").read_text())
    reviewed, report = adjudicate(
        ROOT / config["review_template"], ROOT / config["labels"], config, protocol,
    )
    assert len(reviewed) == 80
    assert reviewed["ticker"].nunique() == 23
    assert report["valid_rows"] == 73
    assert report["invalid_rows"] == 7
    assert report["source_precision"] == 0.9125
    assert report["wilson_95_lower_bound"] < protocol["review_gate"]["minimum_wilson_95_lower_bound"]
    assert report["review_gate_passed"] is False
    assert report["ready_to_build_revision_pairs"] is False
    assert report["ready_for_direction_preregistration"] is False


def test_v9_failures_are_new_generalization_errors() -> None:
    labels = pd.read_csv(ROOT / "data/herd/sec_guidance_structure_v9_review_labels.csv")
    reasons = set(labels.loc[labels["review_decision"].eq("INVALID"), "review_reason"])
    assert "NEXT_YEAR_GUIDANCE_MAPPED_TO_PRIOR_YEAR" in reasons
    assert "NON_GAAP_NARRATIVE_MISCLASSIFIED_AS_GAAP" in reasons
    assert "REPORTED_BASIS_NOT_BOUND_TO_GAAP" in reasons
    assert "EXCLUDING_ITEMS_BASIS_LEFT_UNSPECIFIED" in reasons
    assert "FULL_YEAR_GUIDANCE_MAPPED_TO_REPORTING_QUARTER" in reasons
    assert "PREVIOUS_PRELIMINARY_GUIDANCE_SELECTED_AS_CURRENT" in reasons
