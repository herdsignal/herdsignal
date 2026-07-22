import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_block_source_review_v1 import adjudicate


ROOT = Path(__file__).resolve().parents[2]


def test_v7_locked_source_review_fails_without_opening_revision_pairs() -> None:
    config = json.loads((ROOT / "data/herd/sec_guidance_structure_v7_review.json").read_text())
    protocol = json.loads((ROOT / "data/herd/sec_guidance_v7_independent_validation.json").read_text())
    reviewed, report = adjudicate(
        ROOT / config["review_template"], ROOT / config["labels"], config, protocol,
    )
    invalid = reviewed.loc[reviewed["review_decision"].eq("INVALID")]

    assert len(reviewed) == 80
    assert reviewed["ticker"].nunique() == 24
    assert len(invalid) == 12
    assert report["valid_rows"] == 68
    assert report["source_precision"] == 0.85
    assert report["wilson_95_lower_bound"] < protocol["review_gate"]["minimum_wilson_95_lower_bound"]
    assert report["review_gate_passed"] is False
    assert report["ready_to_build_revision_pairs"] is False


def test_v7_failure_reasons_cover_period_role_and_metric_errors() -> None:
    labels = pd.read_csv(ROOT / "data/herd/sec_guidance_structure_v7_review_labels.csv")
    reasons = set(labels.loc[labels["review_decision"].eq("INVALID"), "review_reason"])
    assert "REPORTING_PERIOD_MAPPED_TO_WRONG_FISCAL_YEAR" in reasons
    assert "LAST_DISCLOSED_RANGE_SELECTED_AS_CURRENT" in reasons
    assert "ORGANIC_GROWTH_RANGE_MISCLASSIFIED_AS_EPS" in reasons
    assert "HISTORICAL_GUIDANCE_SELECTED_AS_CURRENT" in reasons
