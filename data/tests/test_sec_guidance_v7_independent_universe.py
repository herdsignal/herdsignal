import json
import hashlib
from pathlib import Path

import pandas as pd

from herd.sec_guidance_v7_independent_universe import select_v7_universe
from herd.sec_guidance_v7_filing_selection import select_filings


ROOT = Path(__file__).resolve().parents[2]


def test_v7_universe_is_remaining_deterministic_outcome_blind_population() -> None:
    universe, report = select_v7_universe()
    prior = set(pd.read_csv(ROOT / "data/reports/sec_guidance_v5_broad_metadata_universe.csv")["ticker"].astype(str))
    prior.update(pd.read_csv(ROOT / "data/reports/sec_guidance_v6_third_wave_metadata.csv")["ticker"].astype(str))
    assert len(universe) == 201
    assert universe["gics_sector"].nunique() == 9
    assert set(universe["ticker"].astype(str)).isdisjoint(prior)
    assert report["selection_used_guidance_text"] is False
    assert report["selection_used_parser_output"] is False
    assert report["selection_used_price_outcomes"] is False
    assert report["operational_action_ratio"] == 0


def test_v7_filing_selection_is_capped_and_outcome_blind() -> None:
    universe, catalog, report, protocol = select_filings()
    assert len(universe) == 200
    assert catalog.groupby("ticker").size().max() <= 36
    assert report["selection_used_guidance_text"] is False
    assert report["selection_used_parser_output"] is False
    assert report["selection_used_price_outcomes"] is False
    assert protocol["download"]["include_filename_patterns"]


def test_v7_review_sample_is_locked_before_source_adjudication() -> None:
    report_path = ROOT / "data/reports/sec_guidance_structure_v7.json"
    review_path = ROOT / "data/reports/sec_guidance_structure_v7_review.csv"
    report = json.loads(report_path.read_text())
    review = pd.read_csv(review_path)
    excluded = set()
    protocol = json.loads((ROOT / "data/herd/sec_guidance_v7_independent_validation.json").read_text())
    for path in protocol["development_reviews"]:
        excluded.update(pd.read_csv(ROOT / path)["accession_number"].astype(str))

    assert len(review) == 80
    assert review["ticker"].nunique() >= 20
    assert set(review["review_decision"]) == {"PENDING"}
    assert set(review["accession_number"].astype(str)).isdisjoint(excluded)
    assert hashlib.sha256(review_path.read_bytes()).hexdigest() == report["review_sha256"]
    assert report["review_sample_gate_ready"] is True
    assert report["review_gate_passed"] is False
    assert report["operational_action_ratio"] == 0
