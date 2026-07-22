from pathlib import Path

import pandas as pd

from herd.sec_guidance_structure_parser_v7 import audit_v6_review, transform_candidate


ROOT = Path(__file__).resolve().parents[2]
REVIEW = pd.read_csv(ROOT / "data/reports/sec_guidance_structure_v6_reviewed.csv")


def _row(review_id: str) -> pd.Series:
    return REVIEW.loc[REVIEW["review_id"].eq(review_id)].iloc[0]


def test_range_local_basis_is_corrected() -> None:
    assert transform_candidate(_row("SG6-0008"))["accounting_basis"] == "NON_GAAP"
    assert transform_candidate(_row("SG6-0057"))["accounting_basis"] == "NON_GAAP"
    assert transform_candidate(_row("SG6-0061"))["accounting_basis"] == "NON_GAAP"


def test_range_local_quarter_is_corrected() -> None:
    assert transform_candidate(_row("SG6-0033"))["fiscal_period"] == "Q1-2021"
    assert transform_candidate(_row("SG6-0047"))["fiscal_period"] == "Q2-2018"


def test_qualitative_range_and_ocf_misclassification_are_rejected() -> None:
    assert transform_candidate(_row("SG6-0060")) is None
    assert transform_candidate(_row("SG6-0070")) is None
    assert transform_candidate(_row("SG6-0076")) is None


def test_v7_fixes_all_v6_nonvalid_without_losing_valid_rows() -> None:
    assert audit_v6_review("data/reports/sec_guidance_structure_v6_reviewed.csv") == {
        "v6_nonvalid_audited": 9,
        "v6_nonvalid_dropped": 4,
        "v6_nonvalid_corrected": 5,
        "v6_nonvalid_unchanged": 0,
        "v6_valid_audited": 71,
        "v6_valid_retained": 71,
        "v7_development_regression_passed": True,
    }
