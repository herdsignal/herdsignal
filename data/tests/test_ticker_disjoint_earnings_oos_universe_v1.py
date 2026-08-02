import pandas as pd

from herd.ticker_disjoint_earnings_oos_universe_v1 import select_candidates


def test_selection_is_ticker_disjoint_and_outcome_blind():
    locked = pd.DataFrame([{"ticker": "OLD", "sector_etf": "XLK"}])
    inventory = pd.DataFrame([
        {
            "ticker": "OLD", "company": "Old", "cik": "1",
            "gics_sector": "Tech", "sector_etf": "XLK", "price_rows": 2000,
            "price_start": "2012-01-01", "price_end": "2026-01-01",
        },
        {
            "ticker": "NEW", "company": "New", "cik": "2",
            "gics_sector": "Tech", "sector_etf": "XLK", "price_rows": 1500,
            "price_start": "2020-01-01", "price_end": "2026-01-01",
        },
        {
            "ticker": "SHORT", "company": "Short", "cik": "3",
            "gics_sector": "Tech", "sector_etf": "XLK", "price_rows": 500,
            "price_start": "2024-01-01", "price_end": "2026-01-01",
        },
    ])
    manifest = {"files": {
        "OLD": {"role": "EQUITY"}, "NEW": {"role": "EQUITY"},
        "SHORT": {"role": "EQUITY"},
    }}

    selected = select_candidates(
        locked, inventory, manifest, minimum_sessions=1008
    )

    assert selected["ticker"].tolist() == ["NEW"]
    assert selected["selected_without_future_returns"].all()
