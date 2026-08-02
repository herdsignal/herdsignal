import hashlib
from pathlib import Path

import pandas as pd

from herd.ticker_disjoint_earnings_oos_expansion_v2 import (
    extract_official_sector,
    select_former_constituents,
)


def _write_evidence(root: Path, html: str) -> str:
    payload = html.encode()
    digest = hashlib.sha256(payload).hexdigest()
    (root / f"{digest}.html").write_bytes(payload)
    return digest


def test_selects_only_disjoint_rows_with_event_cik_and_official_sector(tmp_path: Path):
    digest = _write_evidence(
        tmp_path,
        "<table><tr><th>Action</th><th>Ticker</th><th>GICS Sector</th></tr>"
        "<tr><td>Deletion</td><td>GOOD</td><td>Information Technology</td></tr></table>",
    )
    events = pd.DataFrame([
        {"action": "REMOVE", "event_status": "VERIFIED_OFFICIAL_EVENT", "ticker": "GOOD", "cik": "123", "effective_date": "2024-01-01", "sp_source_url": "https://example.test", "sp_source_sha256": digest},
        {"action": "REMOVE", "event_status": "VERIFIED_OFFICIAL_EVENT", "ticker": "NO_CIK", "cik": None, "effective_date": "2024-01-01", "sp_source_url": "https://example.test", "sp_source_sha256": digest},
        {"action": "REMOVE", "event_status": "VERIFIED_OFFICIAL_EVENT", "ticker": "LOCKED", "cik": "456", "effective_date": "2024-01-01", "sp_source_url": "https://example.test", "sp_source_sha256": digest},
    ])

    selected, exclusions = select_former_constituents(events, {"LOCKED"}, set(), tmp_path)

    assert selected["ticker"].tolist() == ["GOOD"]
    assert selected.iloc[0]["cik"] == "0000000123"
    assert selected.iloc[0]["sector_etf"] == "XLK"
    assert selected["selected_without_price_or_earnings_outcomes"].all()
    assert exclusions == {"MISSING_EVENT_TIME_CIK": 1, "MISSING_OFFICIAL_SECTOR": 0}


def test_rejects_tampered_official_evidence(tmp_path: Path):
    digest = _write_evidence(tmp_path, "<table><tr><td>X</td></tr></table>")
    path = tmp_path / f"{digest}.html"
    path.write_text("changed")

    assert extract_official_sector(path, "X") is None
