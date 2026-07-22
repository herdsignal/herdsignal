from pathlib import Path

import pandas as pd

from herd.sec_guidance_v9_historical_filing_selection import END, START, select_filings


ROOT = Path(__file__).resolve().parents[2]


def test_v9_historical_selection_is_time_disjoint_and_outcome_blind() -> None:
    _, selected, report, _ = select_filings()
    v7 = pd.read_csv(ROOT / "data/reports/sec_guidance_v7_filing_catalog.csv")
    v8 = pd.concat([
        pd.read_csv(ROOT / "data/reports/sec_guidance_v8_filing_catalog.csv"),
        pd.read_csv(ROOT / "data/reports/sec_guidance_v8_coverage_completion_catalog.csv"),
    ])
    assert selected["accepted_at"].str[:10].between(START, END).all()
    assert set(selected["accession_number"]).isdisjoint(set(v7["accession_number"]))
    assert set(selected["accession_number"]).isdisjoint(set(v8["accession_number"]))
    assert selected.groupby("ticker").size().max() <= 24
    assert report["selection_used_guidance_text"] is False
    assert report["selection_used_parser_output"] is False
    assert report["selection_used_source_review_labels"] is False
    assert report["selection_used_price_outcomes"] is False
