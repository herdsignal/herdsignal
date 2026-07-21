from pathlib import Path

import pandas as pd
import pytest

from herd.independent_universe_v1 import load_candidates, normalize_ticker


def test_normalize_share_class_for_yahoo():
    assert normalize_ticker(" brk.b ") == "BRK-B"


def test_candidates_exclude_original_equities_and_map_all_sectors(tmp_path: Path):
    source = tmp_path / "members.csv"
    pd.DataFrame([
        {"Symbol": "AAPL", "Security": "Apple", "GICS Sector": "Information Technology", "CIK": "320193"},
        {"Symbol": "BRK.B", "Security": "Berkshire", "GICS Sector": "Financials", "CIK": "1067983"},
        {"Symbol": "O", "Security": "Realty Income", "GICS Sector": "Real Estate", "CIK": "726728"},
    ]).to_csv(source, index=False)
    result = load_candidates(source).set_index("ticker")
    assert bool(result.loc["AAPL", "excluded_original_universe"]) is True
    assert bool(result.loc["BRK-B", "excluded_original_universe"]) is False
    assert result.loc["O", "sector_etf"] == "XLRE"


def test_unknown_sector_fails_closed(tmp_path: Path):
    source = tmp_path / "members.csv"
    pd.DataFrame([{"Symbol": "AAA", "Security": "A", "GICS Sector": "Unknown", "CIK": "1"}]).to_csv(source, index=False)
    with pytest.raises(ValueError, match="unsupported GICS sector"):
        load_candidates(source)
