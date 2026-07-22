import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]


def test_v6_source_review_is_complete_and_fail_closed() -> None:
    report = json.loads((ROOT / "data/reports/sec_guidance_structure_v6_source_review.json").read_text())
    reviewed = pd.read_csv(ROOT / "data/reports/sec_guidance_structure_v6_reviewed.csv")
    labels = ROOT / "data/herd/sec_guidance_structure_v6_review_labels.csv"
    assert len(reviewed) == 80
    assert reviewed["review_decision"].value_counts().to_dict() == {"VALID": 71, "INVALID": 8, "AMBIGUOUS": 1}
    assert report["labels_sha256"] == hashlib.sha256(labels.read_bytes()).hexdigest()
    assert report["review_complete"] is True
    assert report["review_gate_passed"] is False
    assert report["ready_to_build_revision_pairs"] is False
    assert report["ready_for_direction_preregistration"] is False
    assert report["price_outcomes_observed"] is False
    assert report["wilson_95_lower_bound"] < 0.90


def test_v6_failure_taxonomy_covers_new_structural_errors() -> None:
    reviewed = pd.read_csv(ROOT / "data/reports/sec_guidance_structure_v6_reviewed.csv")
    nonvalid = reviewed.loc[reviewed["review_decision"].ne("VALID"), "review_reason"].tolist()
    assert any("BASIS" in reason for reason in nonvalid)
    assert any("QUARTER_GUIDANCE_MAPPED_TO_FULL_YEAR" == reason for reason in nonvalid)
    assert any("QUALITATIVE_HIGH_END" in reason for reason in nonvalid)
    assert any("OPERATING_CASH_FLOW_MISCLASSIFIED" in reason for reason in nonvalid)
