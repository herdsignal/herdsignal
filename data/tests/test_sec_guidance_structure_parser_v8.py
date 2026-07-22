from pathlib import Path

import pandas as pd

from herd.sec_guidance_structure_parser_v8 import audit_v7_review, transform_candidate


ROOT = Path(__file__).resolve().parents[2]
REVIEW = pd.read_csv(ROOT / "data/reports/sec_guidance_structure_v7_reviewed.csv")


def _row(review_id: str) -> pd.Series:
    return REVIEW.loc[REVIEW["review_id"].eq(review_id)].iloc[0]


def test_v8_rejects_prior_and_last_disclosed_ranges() -> None:
    for review_id in ("SG7-0021", "SG7-0050", "SG7-0054", "SG7-0055"):
        assert transform_candidate(_row(review_id)) is None
    assert transform_candidate(_row("SG7-0066")) is not None


def test_v8_corrects_or_rejects_reporting_period_errors() -> None:
    assert transform_candidate(_row("SG7-0016"))["fiscal_period"] == "FY2018"
    assert transform_candidate(_row("SG7-0017"))["fiscal_period"] == "FY2018"
    assert transform_candidate(_row("SG7-0041")) is None
    assert transform_candidate(_row("SG7-0043"))["fiscal_period"] == "FY2023"
    assert transform_candidate(_row("SG7-0075"))["fiscal_period"] == "Q1-2018"
    assert transform_candidate(_row("SG7-0080")) is None


def test_v8_rejects_percent_growth_ranges_misclassified_as_eps() -> None:
    assert transform_candidate(_row("SG7-0028")) is None
    assert transform_candidate(_row("SG7-0033")) is None


def test_v8_fixes_all_v7_nonvalid_without_losing_valid_rows() -> None:
    assert audit_v7_review("data/reports/sec_guidance_structure_v7_reviewed.csv") == {
        "v7_nonvalid_audited": 12,
        "v7_nonvalid_dropped": 8,
        "v7_nonvalid_corrected": 4,
        "v7_nonvalid_unchanged": 0,
        "v7_valid_audited": 68,
        "v7_valid_retained": 68,
        "v7_valid_changed": 0,
        "v8_development_regression_passed": True,
    }
