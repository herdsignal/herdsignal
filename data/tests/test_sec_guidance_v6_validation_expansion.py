import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "data/herd/sec_guidance_v6_validation_expansion.json").read_text())


def test_expansion_preserves_locked_review_and_requires_eight_new_issuers() -> None:
    review = pd.read_csv(ROOT / "data/reports/sec_guidance_structure_v6_expanded_review.csv")
    report = json.loads((ROOT / "data/reports/sec_guidance_structure_v6_expansion.json").read_text())
    locked = pd.read_csv(ROOT / PROTOCOL["locked_v6_review"])
    columns = list(locked.columns)
    pd.testing.assert_frame_equal(
        review.iloc[:len(locked)][columns].reset_index(drop=True),
        locked[columns].reset_index(drop=True),
        check_dtype=False,
    )
    assert report["new_v6_candidate_tickers"] >= PROTOCOL["review_gate"]["minimum_new_candidate_tickers"]
    assert report["expanded_review_new_tickers"] >= PROTOCOL["review_gate"]["minimum_new_candidate_tickers"]
    assert report["expanded_review_rows"] >= PROTOCOL["review_gate"]["minimum_stratified_rows"]
    assert report["expanded_review_tickers"] >= PROTOCOL["review_gate"]["minimum_distinct_tickers"]
    assert report["review_sample_gate_ready"] is True
    assert report["review_gate_passed"] is False
    assert report["price_outcomes_observed"] is False
    assert report["operational_action_ratio"] == 0
