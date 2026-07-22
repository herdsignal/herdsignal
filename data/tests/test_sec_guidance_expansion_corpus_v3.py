import json
from pathlib import Path

from herd.sec_guidance_expansion_corpus_v3 import candidate_universe, select_expansion


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "data/herd/sec_guidance_expansion_corpus_v3.json").read_text())


def test_expansion_universe_is_disjoint_from_original_tickers() -> None:
    original = set(__import__("pandas").read_csv(ROOT / PROTOCOL["exclude_universe"])["ticker"])
    expansion = candidate_universe(PROTOCOL)
    assert set(expansion["ticker"]).isdisjoint(original)
    assert expansion["cik"].is_unique


def test_selection_uses_only_filing_coverage() -> None:
    universe, catalog, report = select_expansion(PROTOCOL)
    assert len(universe) == PROTOCOL["target_tickers"]
    assert set(catalog["ticker"]) == set(universe["ticker"])
    assert catalog.groupby("ticker").size().eq(PROTOCOL["collection_filings_per_ticker"]).all()
    assert report["selection_used_guidance_text"] is False
    assert report["selection_used_price_outcomes"] is False


def test_collected_expansion_corpus_is_complete() -> None:
    corpus = ROOT / "data/reference/sec/sec-8k-guidance-expansion-v3-60-20260722"
    manifest = json.loads((corpus / "manifest.json").read_text())
    assert manifest["filings_collected"] == manifest["filings_requested"] == 2160
    assert manifest["failures"] == []
    assert manifest["guidance_direction_classified"] == 0
