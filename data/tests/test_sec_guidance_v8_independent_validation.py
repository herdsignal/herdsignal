import hashlib
import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_v8_independent_validation import build
from herd.sec_guidance_v8_filing_selection import select_filings


ROOT = Path(__file__).resolve().parents[2]


def test_v8_holdout_excludes_every_prior_review_accession() -> None:
    protocol = json.loads((ROOT / "data/herd/sec_guidance_v8_independent_validation.json").read_text())
    _, review, report = build(protocol)
    excluded = set()
    for path in protocol["development_reviews"]:
        excluded.update(pd.read_csv(ROOT / path)["accession_number"].astype(str))
    assert set(review["accession_number"].astype(str)).isdisjoint(excluded)
    assert set(review["review_decision"]) == {"PENDING"}
    assert report["price_outcomes_observed"] is False
    assert report["operational_action_ratio"] == 0


def test_frozen_v8_sample_matches_report_hash_when_ready() -> None:
    report_path = ROOT / "data/reports/sec_guidance_structure_v8.json"
    review_path = ROOT / "data/reports/sec_guidance_structure_v8_review.csv"
    if not report_path.exists() or not review_path.exists():
        return
    report = json.loads(report_path.read_text())
    review = pd.read_csv(review_path)
    assert hashlib.sha256(review_path.read_bytes()).hexdigest() == report["review_sha256"]
    if report["review_sample_gate_ready"]:
        assert len(review) >= 80
        assert review["ticker"].nunique() >= 20


def test_v8_second_wave_filings_do_not_overlap_v7() -> None:
    selected, report, _ = select_filings()
    v7 = pd.read_csv(ROOT / "data/reports/sec_guidance_v7_filing_catalog.csv")
    assert set(selected["accession_number"]).isdisjoint(set(v7["accession_number"]))
    assert selected.groupby("ticker").size().max() <= 36
    assert report["selection_used_guidance_text"] is False
    assert report["selection_used_parser_output"] is False
    assert report["selection_used_price_outcomes"] is False
    assert report["selected_tickers"] >= 20
