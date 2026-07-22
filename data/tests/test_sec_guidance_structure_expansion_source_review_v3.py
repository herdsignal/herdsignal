import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]


def test_locked_unseen_review_is_complete_and_independent() -> None:
    report = json.loads(
        (ROOT / "data/reports/sec_guidance_structure_expansion_source_review_v3.json").read_text()
    )
    reviewed = pd.read_csv(ROOT / "data/reports/sec_guidance_structure_expansion_reviewed_v3.csv")

    assert report["reviewed_rows"] == len(reviewed) == 80
    assert report["distinct_tickers"] == reviewed["ticker"].nunique() == 24
    assert report["review_complete"] is True
    assert report["price_outcomes_observed"] is False


def test_v3_fails_closed_below_locked_precision_gate() -> None:
    report = json.loads(
        (ROOT / "data/reports/sec_guidance_structure_expansion_source_review_v3.json").read_text()
    )

    assert report["source_precision"] == 54 / 80
    assert report["wilson_95_lower_bound"] < 0.9
    assert report["review_gate_passed"] is False
    assert report["ready_to_build_revision_pairs"] is False
    assert report["ready_for_direction_preregistration"] is False


def test_known_structural_false_positives_are_rejected() -> None:
    reviewed = pd.read_csv(ROOT / "data/reports/sec_guidance_structure_expansion_reviewed_v3.csv")
    decisions = reviewed.set_index("review_id")["review_decision"]

    for review_id in ["SG3X-0002", "SG3X-0036", "SG3X-0045", "SG3X-0068", "SG3X-0080"]:
        assert decisions[review_id] == "INVALID"
