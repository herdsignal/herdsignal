import json
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
