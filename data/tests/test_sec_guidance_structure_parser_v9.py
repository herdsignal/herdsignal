from pathlib import Path

import pandas as pd

from herd.sec_guidance_structure_parser_v9 import audit_v8_review, transform_candidate


ROOT = Path(__file__).resolve().parents[2]
REVIEW = pd.read_csv(ROOT / "data/reports/sec_guidance_structure_v8_reviewed.csv")


def _row(review_id: str) -> pd.Series:
    return REVIEW.loc[REVIEW["review_id"].eq(review_id)].iloc[0]


def test_v9_rejects_non_guidance_and_prior_ranges() -> None:
    for review_id in ("SG8-0021", "SG8-0025", "SG8-0033", "SG8-0043"):
        assert transform_candidate(_row(review_id)) is None


def test_v9_binds_respectively_and_row_local_basis() -> None:
    for review_id in ("SG8-0024", "SG8-0028"):
        assert transform_candidate(_row(review_id))["accounting_basis"] == "UNSPECIFIED"
    assert transform_candidate(_row("SG8-0039"))["accounting_basis"] == "NON_GAAP"
    assert transform_candidate(_row("SG8-0041"))["accounting_basis"] == "NON_GAAP"


def test_v9_binds_reaffirmed_annual_period() -> None:
    assert transform_candidate(_row("SG8-0044"))["fiscal_period"] == "FY2024"


def test_v9_keeps_corrected_v8_source_label_semantics() -> None:
    transformed = transform_candidate(_row("SG8-0048"))
    assert transformed is not None
    for field in ("fiscal_period", "accounting_basis", "metric", "unit", "lower_bound", "upper_bound"):
        assert str(transformed[field]) == str(_row("SG8-0048")[field])


def test_v9_repairs_all_eight_v8_errors_without_changing_valid_rows() -> None:
    assert audit_v8_review("data/reports/sec_guidance_structure_v8_reviewed.csv") == {
        "v8_invalid_audited": 8,
        "v8_invalid_dropped": 4,
        "v8_invalid_corrected": 4,
        "v8_invalid_unchanged": 0,
        "v8_valid_audited": 72,
        "v8_valid_retained": 72,
        "v8_valid_changed": 0,
        "v9_development_regression_passed": True,
    }
