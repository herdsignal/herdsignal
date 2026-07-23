import hashlib
import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_v10_independent_validation import build


ROOT = Path(__file__).resolve().parents[2]


def test_v10_holdout_excludes_all_prior_review_accessions() -> None:
    protocol = json.loads((ROOT / "data/herd/sec_guidance_v10_independent_validation.json").read_text())
    _, review, report = build(protocol)
    excluded = set()
    for path in protocol["development_reviews"]:
        excluded.update(pd.read_csv(ROOT / path)["accession_number"].astype(str))
    assert set(review["accession_number"].astype(str)).isdisjoint(excluded)
    assert set(review["review_decision"]) == {"PENDING"}
    assert report["v10_development_regression_passed"] is True
    assert report["price_outcomes_observed"] is False
    assert report["operational_action_ratio"] == 0


def test_v10_locked_sample_hash_and_gate() -> None:
    report_path = ROOT / "data/reports/sec_guidance_structure_v10.json"
    review_path = ROOT / "data/reports/sec_guidance_structure_v10_review.csv"
    candidate_path = ROOT / "data/reports/sec_guidance_structure_v10_candidates.csv"
    report = json.loads(report_path.read_text())
    review = pd.read_csv(review_path)
    assert hashlib.sha256(review_path.read_bytes()).hexdigest() == report["review_sha256"]
    assert hashlib.sha256(candidate_path.read_bytes()).hexdigest() == report["candidate_sha256"]
    if report["review_sample_gate_ready"]:
        assert len(review) >= 80
        assert review["ticker"].nunique() >= 20
