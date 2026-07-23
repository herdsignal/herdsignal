from pathlib import Path

import pandas as pd

from herd.sec_guidance_structure_parser_v10 import audit_v9_review, transform_candidate


ROOT = Path(__file__).resolve().parents[2]
REVIEW = pd.read_csv(ROOT / "data/reports/sec_guidance_structure_v9_reviewed.csv")


def _row(review_id: str) -> pd.Series:
    return REVIEW.loc[REVIEW["review_id"].eq(review_id)].iloc[0]


def test_v10_binds_explicit_forward_full_year_header() -> None:
    for review_id in ("SG9-0002", "SG9-0055"):
        assert transform_candidate(_row(review_id))["fiscal_period"] == "FY2012"


def test_v10_binds_narrative_and_row_accounting_basis() -> None:
    assert transform_candidate(_row("SG9-0011"))["accounting_basis"] == "NON_GAAP"
    assert transform_candidate(_row("SG9-0018"))["accounting_basis"] == "GAAP"
    assert transform_candidate(_row("SG9-0019"))["accounting_basis"] == "NON_GAAP"


def test_v10_binds_annual_action_and_rejects_previous_preliminary_range() -> None:
    assert transform_candidate(_row("SG9-0024"))["fiscal_period"] == "FY2024"
    assert transform_candidate(_row("SG9-0049")) is None


def test_v10_repairs_all_v9_errors_without_changing_valid_rows() -> None:
    assert audit_v9_review("data/reports/sec_guidance_structure_v9_reviewed.csv") == {
        "v9_invalid_audited": 7,
        "v9_invalid_dropped": 1,
        "v9_invalid_corrected": 6,
        "v9_invalid_unchanged": 0,
        "v9_valid_audited": 73,
        "v9_valid_retained": 73,
        "v9_valid_changed": 0,
        "v10_development_regression_passed": True,
    }
