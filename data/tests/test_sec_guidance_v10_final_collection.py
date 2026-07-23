import json
from pathlib import Path

from herd.sec_guidance_v10_final_collection import select_filings


ROOT = Path(__file__).resolve().parents[2]


def test_v10_final_collection_is_outcome_blind_and_bounded() -> None:
    protocol = json.loads((ROOT / "data/herd/sec_guidance_v10_final_collection.json").read_text())
    universe, catalog, report, _ = select_filings(protocol)
    expansion = json.loads((ROOT / protocol["expansion_contract"]).read_text())
    assert len(universe) <= protocol["filing_target_tickers"]
    assert catalog.groupby("ticker").size().max() <= expansion["collection_filings_per_ticker"]
    assert set(catalog["ticker"]).issubset(set(universe["ticker"]))
    assert report["selection_used_guidance_text"] is False
    assert report["selection_used_parser_output"] is False
    assert report["selection_used_source_review_labels"] is False
    assert report["selection_used_price_outcomes"] is False
