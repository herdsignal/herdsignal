import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_v6_issuer_expansion import _exclusions, select_expansion, select_supplement


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "data/herd/sec_guidance_v6_issuer_expansion.json").read_text())


def test_v6_expansion_is_new_issuer_accession_and_outcome_blind() -> None:
    universe, catalog, report = select_expansion(PROTOCOL)
    excluded_tickers, excluded_accessions = _exclusions(PROTOCOL)
    assert len(universe) == PROTOCOL["target_tickers"]
    assert universe["gics_sector"].nunique() == 11
    assert set(universe["ticker"].astype(str)).isdisjoint(excluded_tickers)
    assert set(catalog["accession_number"].astype(str)).isdisjoint(excluded_accessions)
    assert set(catalog["ticker"].astype(str)) == set(universe["ticker"].astype(str))
    assert report["selection_used_guidance_text"] is False
    assert report["selection_used_parser_output"] is False
    assert report["selection_used_price_outcomes"] is False
    assert report["scope"] == "PARSER_VALIDATION_ONLY"
    assert report["operational_action_ratio"] == 0


def test_supplement_uses_only_remaining_locked_metadata_issuers() -> None:
    supplement, catalog, report = select_supplement(
        PROTOCOL, ROOT / "data/reports/sec_guidance_v6_issuer_universe.csv",
    )
    collected = set(pd.read_csv(ROOT / "data/reports/sec_guidance_v6_issuer_universe.csv")["ticker"].astype(str))
    assert len(supplement) == 9
    assert set(supplement["ticker"].astype(str)).isdisjoint(collected)
    assert set(catalog["ticker"].astype(str)) == set(supplement["ticker"].astype(str))
    assert report["selection_used_guidance_text"] is False
    assert report["selection_used_parser_output"] is False
    assert report["selection_used_price_outcomes"] is False
