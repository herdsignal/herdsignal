import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_v4_issuer_expansion import select_issuers


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "data/herd/sec_guidance_v5_issuer_expansion.json").read_text())


def test_v5_expansion_exhausts_unseen_local_pool_without_outcome_selection() -> None:
    universe, catalog, report = select_issuers(PROTOCOL)
    excluded = set()
    for path in [PROTOCOL["prior_expansion_universe"], *PROTOCOL["additional_exclude_universes"]]:
        excluded.update(pd.read_csv(ROOT / path)["ticker"].astype(str))
    for path in PROTOCOL["review_ledgers"]:
        excluded.update(pd.read_csv(ROOT / path)["ticker"].astype(str))

    assert len(universe) == report["selected_tickers"] == 23
    assert report["eligible_unseen_tickers"] == 26
    assert set(universe["ticker"]).isdisjoint(excluded)
    assert catalog.groupby("ticker").size().le(PROTOCOL["collection_filings_per_ticker"]).all()
    assert catalog.groupby("ticker").size().ge(PROTOCOL["minimum_eligible_filings_per_ticker"]).all()
    assert report["selection_used_parser_output"] is False
    assert report["selection_used_guidance_text"] is False
    assert report["selection_used_price_outcomes"] is False
