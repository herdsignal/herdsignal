import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_v5_broad_expansion import select_metadata_universe


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "data/herd/sec_guidance_v5_broad_expansion.json").read_text())


def test_metadata_selection_is_balanced_and_outcome_blind() -> None:
    selected, report = select_metadata_universe(PROTOCOL)
    excluded = set()
    for path in [*PROTOCOL["exclude_universes"], *PROTOCOL["review_ledgers"]]:
        excluded.update(pd.read_csv(ROOT / path)["ticker"].astype(str))
    assert len(selected) == PROTOCOL["metadata_target_tickers"]
    assert selected["gics_sector"].nunique() == 11
    assert set(selected["ticker"]).isdisjoint(excluded)
    assert selected["cik"].str.fullmatch(r"\d{10}").all()
    assert report["selection_used_guidance_text"] is False
    assert report["selection_used_parser_output"] is False
    assert report["selection_used_price_outcomes"] is False
    assert report["scope"] == "PARSER_VALIDATION_ONLY"
