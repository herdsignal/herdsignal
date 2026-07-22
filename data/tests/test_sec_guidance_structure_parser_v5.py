import hashlib
import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_structure_parser_v5 import audit_v4_nonvalid_bindings, transform_candidate


ROOT = Path(__file__).resolve().parents[2]
V4 = pd.read_csv(ROOT / "data/reports/sec_guidance_structure_v4_candidates.csv")


def _row(ticker: str, accession: str, low: float) -> pd.Series:
    rows = V4.loc[
        V4["ticker"].eq(ticker)
        & V4["accession_number"].astype(str).eq(accession)
        & V4["lower_bound"].sub(low).abs().lt(1e-6 * max(1, abs(low)))
    ]
    assert len(rows) == 1
    return rows.iloc[0]


def test_compact_quarter_overrides_full_year() -> None:
    transformed = transform_candidate(_row("JBL", "0001193125-23-305726", 0.47))
    assert transformed is not None
    assert transformed["fiscal_period"] == "Q2-2024"


def test_prior_ranges_are_removed() -> None:
    assert transform_candidate(_row("ABBV", "0001104659-16-135186", 4.62)) is None
    assert transform_candidate(_row("FLS", "0001193125-25-167111", 3.10)) is None
    assert transform_candidate(_row("PODD", "0001157523-17-002282", 425e6)) is None


def test_basis_and_subtype_are_bound() -> None:
    hon = transform_candidate(_row("HON", "0000930413-16-005153", 6.45))
    lumen = transform_candidate(_row("LUMN", "0001193125-18-242795", 1.3e9))
    assert hon is not None and hon["accounting_basis"] == "NON_GAAP"
    assert lumen is not None and lumen["metric_subtype"] == "AFTER_DIVIDENDS"


def test_multi_basis_single_range_is_rejected() -> None:
    assert transform_candidate(_row("LLY", "0001193125-12-002878", 3.10)) is None


def test_v5_sample_excludes_every_v4_review_accession() -> None:
    review = pd.read_csv(ROOT / "data/reports/sec_guidance_structure_v5_review.csv")
    v4_reviewed = set(pd.read_csv(ROOT / "data/reports/sec_guidance_structure_v4_reviewed.csv")["accession_number"].astype(str))
    assert set(review["accession_number"].astype(str)).isdisjoint(v4_reviewed)
    report = json.loads((ROOT / "data/reports/sec_guidance_structure_v5.json").read_text())
    review_path = ROOT / "data/reports/sec_guidance_structure_v5_review.csv"
    assert report["fresh_review_candidate_sha256"] == hashlib.sha256(review_path.read_bytes()).hexdigest()
    assert report["review_sample_gate_ready"] is True
    assert report["review_gate_passed"] is False
    assert report["price_outcomes_observed"] is False
    assert report["operational_action_ratio"] == 0


def test_every_v4_nonvalid_binding_is_corrected_or_rejected() -> None:
    audit = audit_v4_nonvalid_bindings("data/reports/sec_guidance_structure_v4_reviewed.csv")
    assert audit == {
        "v4_nonvalid_bindings_audited": 16,
        "v4_nonvalid_bindings_dropped": 8,
        "v4_nonvalid_bindings_corrected": 8,
        "v4_nonvalid_bindings_unchanged": 0,
        "v4_development_regression_passed": True,
    }
