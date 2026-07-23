import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_v10_final_expansion import select_metadata_universe


ROOT = Path(__file__).resolve().parents[2]


def test_v10_final_expansion_is_unseen_and_deterministic() -> None:
    protocol = json.loads((ROOT / "data/herd/sec_guidance_v10_final_expansion.json").read_text())
    first, report = select_metadata_universe(protocol)
    second, _ = select_metadata_universe(protocol)
    pd.testing.assert_frame_equal(first, second)
    existing = pd.read_csv(ROOT / protocol["existing_universe"], dtype={"cik": str})
    assert set(first["ticker"]).isdisjoint(existing["ticker"].astype(str))
    assert set(first["cik"]).isdisjoint(existing["cik"].dropna().astype(str).str.zfill(10))
    assert len(first) == protocol["metadata_target_tickers"]
    assert report["selection_used_guidance_text"] is False
    assert report["selection_used_parser_output"] is False
    assert report["selection_used_price_outcomes"] is False


def test_v10_final_expansion_uses_plain_exchange_tickers() -> None:
    protocol = json.loads((ROOT / "data/herd/sec_guidance_v10_final_expansion.json").read_text())
    selected, _ = select_metadata_universe(protocol)
    assert selected["ticker"].str.fullmatch(r"[A-Z]{1,5}").all()
    assert set(selected["exchange"]).issubset(set(protocol["exchanges"]))
