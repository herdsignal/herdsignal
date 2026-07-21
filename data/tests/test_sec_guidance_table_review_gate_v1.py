import pandas as pd

from herd.sec_guidance_table_review_gate_v1 import evaluate, wilson_lower


PROTOCOL = {
    "review_gate": {
        "minimum_stratified_rows": 60,
        "minimum_wilson_95_lower_bound": 0.90,
    }
}


def test_wilson_lower_requires_more_than_point_precision():
    assert wilson_lower(60, 60) > 0.93
    assert wilson_lower(57, 60) < 0.90


def test_pending_review_cannot_pass():
    review = pd.DataFrame({"review_decision": ["PENDING"] * 60})
    result = evaluate(review, PROTOCOL)
    assert result["review_complete"] is False
    assert result["review_gate_passed"] is False
    assert result["ready_for_direction_preregistration"] is False


def test_complete_high_precision_review_only_opens_pair_building():
    review = pd.DataFrame({"review_decision": ["VALID"] * 60})
    result = evaluate(review, PROTOCOL)
    assert result["review_gate_passed"] is True
    assert result["ready_to_build_revision_pairs"] is True
    assert result["ready_for_direction_preregistration"] is False


def test_optional_ticker_diversity_is_part_of_completion():
    protocol = {"review_gate": {**PROTOCOL["review_gate"], "minimum_distinct_tickers": 20}}
    review = pd.DataFrame({"review_decision": ["VALID"] * 60, "ticker": ["ONE"] * 60})
    result = evaluate(review, protocol)
    assert result["ticker_requirement_met"] is False
    assert result["review_complete"] is False
