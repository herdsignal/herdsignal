import hashlib
import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_v10_final_validation import build


ROOT = Path(__file__).resolve().parents[2]


def test_v10_final_sample_is_fresh_locked_and_outcome_blind() -> None:
    protocol = json.loads((ROOT / "data/herd/sec_guidance_v10_final_validation.json").read_text())
    _, review, report = build(protocol)
    excluded = set()
    for path in protocol["development_reviews"]:
        excluded.update(pd.read_csv(ROOT / path)["accession_number"].astype(str))
    assert set(review["accession_number"].astype(str)).isdisjoint(excluded)
    assert set(review["review_decision"]) == {"PENDING"}
    assert report["corpus_integrity_passed"] is True
    assert report["price_outcomes_observed"] is False
    assert report["operational_action_ratio"] == 0


def test_v10_final_locked_artifact_hashes() -> None:
    report = json.loads((ROOT / "data/reports/sec_guidance_structure_v10_final.json").read_text())
    candidate = ROOT / "data/reports/sec_guidance_structure_v10_final_candidates.csv"
    review = ROOT / "data/reports/sec_guidance_structure_v10_final_review.csv"
    assert hashlib.sha256(candidate.read_bytes()).hexdigest() == report["candidate_sha256"]
    assert hashlib.sha256(review.read_bytes()).hexdigest() == report["review_sha256"]
    if report["review_sample_gate_ready"]:
        frame = pd.read_csv(review)
        assert len(frame) >= 80
        assert frame["ticker"].nunique() >= 20
        assert frame.loc[frame["v10_candidate_origin"].eq("FINAL_EXPANSION"), "ticker"].nunique() >= 4
