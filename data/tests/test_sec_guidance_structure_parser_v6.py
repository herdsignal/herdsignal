import hashlib
import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_structure_parser_v6 import SourceLocator, audit_v5_review, transform_candidate


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "data/herd/sec_guidance_structure_parser_v6.json").read_text())
REVIEW = pd.read_csv(ROOT / "data/reports/sec_guidance_structure_v5_reviewed.csv")
LOCATOR = SourceLocator(PROTOCOL["source_corpora"])


def _review(review_id: str) -> pd.Series:
    rows = REVIEW.loc[REVIEW["review_id"].eq(review_id)]
    assert len(rows) == 1
    return rows.iloc[0]


def test_current_prior_column_and_initial_guidance_are_rejected() -> None:
    for review_id in ("SG5-0021", "SG5-0022", "SG5-0055", "SG5-0059"):
        assert transform_candidate(_review(review_id), LOCATOR) is None


def test_reporting_and_comparison_periods_do_not_override_forecast_period() -> None:
    dal = transform_candidate(_review("SG5-0068"), LOCATOR)
    app = transform_candidate(_review("SG5-0071"), LOCATOR)
    zbh = transform_candidate(_review("SG5-0074"), LOCATOR)
    assert dal is not None and dal["fiscal_period"] == "Q4-2023"
    assert app is not None and app["fiscal_period"] == "Q1-2023"
    assert zbh is not None and zbh["fiscal_period"] == "FY2017"
    assert transform_candidate(_review("SG5-0070"), LOCATOR) is None
    assert transform_candidate(_review("SG5-0072"), LOCATOR) is None


def test_reported_basis_is_bound_to_its_exact_range() -> None:
    transformed = transform_candidate(_review("SG5-0012"), LOCATOR)
    assert transformed is not None
    assert transformed["accounting_basis"] == "GAAP"


def test_all_v5_failures_are_corrected_without_dropping_valid_rows() -> None:
    audit = audit_v5_review(
        str(ROOT / "data/reports/sec_guidance_structure_v5_reviewed.csv"),
        LOCATOR,
    )
    assert audit == {
        "v5_invalid_bindings_audited": 10,
        "v5_invalid_bindings_dropped": 6,
        "v5_invalid_bindings_corrected": 4,
        "v5_invalid_bindings_unchanged": 0,
        "v5_valid_bindings_audited": 70,
        "v5_valid_bindings_retained": 70,
        "v5_development_regression_passed": True,
    }


def test_v6_review_is_fresh_and_remains_fail_closed() -> None:
    report = json.loads((ROOT / "data/reports/sec_guidance_structure_v6.json").read_text())
    review_path = ROOT / "data/reports/sec_guidance_structure_v6_review.csv"
    review = pd.read_csv(review_path)
    excluded = set()
    for path in PROTOCOL["development_reviews"]:
        excluded.update(pd.read_csv(ROOT / path)["accession_number"].astype(str))
    assert set(review["accession_number"].astype(str)).isdisjoint(excluded)
    assert report["fresh_review_candidate_sha256"] == hashlib.sha256(review_path.read_bytes()).hexdigest()
    assert report["review_sample_gate_ready"] is False
    assert report["review_gate_passed"] is False
    assert report["ready_for_direction_preregistration"] is False
    assert report["operational_action_ratio"] == 0
