import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_v4_issuer_expansion import select_issuers


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "data/herd/sec_guidance_v4_issuer_expansion.json").read_text())


def test_expansion_selection_is_issuer_independent() -> None:
    universe, catalog, report = select_issuers(PROTOCOL)
    reviewed = set()
    for path in PROTOCOL["review_ledgers"]:
        reviewed.update(pd.read_csv(ROOT / path)["ticker"].astype(str))
    reviewed.update(pd.read_csv(ROOT / PROTOCOL["frozen_pre_expansion_review_tickers"])["ticker"].astype(str))
    prior = set(pd.read_csv(ROOT / PROTOCOL["prior_expansion_universe"])["ticker"].astype(str))

    assert len(universe) == PROTOCOL["target_tickers"] == 30
    assert set(universe["ticker"]).isdisjoint(reviewed | prior)
    assert catalog.groupby("ticker").size().eq(PROTOCOL["collection_filings_per_ticker"]).all()
    assert report["selection_used_parser_output"] is False
    assert report["selection_used_guidance_text"] is False
    assert report["selection_used_price_outcomes"] is False


def test_collected_v4_expansion_corpus_is_complete() -> None:
    corpus = ROOT / "data/reference/sec/sec-8k-guidance-v4-extra-30-20260722"
    manifest = json.loads((corpus / "manifest.json").read_text())
    index = pd.read_csv(corpus / "index.csv")

    assert manifest["filings_collected"] == manifest["filings_requested"] == 1080
    assert manifest["failures"] == []
    assert index["accession_number"].nunique() == 1080
    assert index["ticker"].nunique() == 30
    assert manifest["guidance_direction_classified"] == 0
    assert manifest["operational_action_ratio"] == 0
