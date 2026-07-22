import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]


def test_v9_historical_candidates_are_fresh_and_gate_is_honest() -> None:
    report_path = ROOT / "data/reports/sec_guidance_structure_v9_historical.json"
    review_path = ROOT / "data/reports/sec_guidance_structure_v9_historical_review.csv"
    candidate_path = ROOT / "data/reports/sec_guidance_structure_v9_historical_candidates.csv"
    report = json.loads(report_path.read_text())
    review = pd.read_csv(review_path)
    candidates = pd.read_csv(candidate_path)
    v8 = pd.read_csv(ROOT / "data/reports/sec_guidance_structure_v8_reviewed.csv")
    assert hashlib.sha256(review_path.read_bytes()).hexdigest() == report["review_sha256"]
    assert hashlib.sha256(candidate_path.read_bytes()).hexdigest() == report["candidate_sha256"]
    assert set(candidates["accession_number"].astype(str)).isdisjoint(
        set(v8["accession_number"].astype(str))
    )
    assert len(review) == 80
    assert review["ticker"].nunique() == 19
    assert report["review_sample_gate_ready"] is False
    assert set(review["review_decision"]) == {"PENDING"}
