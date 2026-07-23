import json
from pathlib import Path

import pandas as pd

from herd.rush_downside_asymmetry_universe_v1 import build_universe, load_protocol


def test_protocol_forbids_tuning_and_actions():
    protocol = load_protocol()
    assert protocol["policy"]["threshold_tuning_after_results"] is False
    assert protocol["policy"]["operational_action_authority"] is False
    assert protocol["failure_gate"]["all_conditions_required"] is True


def test_universe_excludes_every_discovery_ticker(monkeypatch, tmp_path: Path):
    audit = tmp_path / "audit.csv"
    events = tmp_path / "events.csv"
    protocol = tmp_path / "protocol.json"
    snapshot = tmp_path / "snapshot"
    pd.DataFrame([
        {"ticker": "OLD", "sector_etf": "XLK", "price_rows": 2000},
        {"ticker": "NEW", "sector_etf": "XLI", "price_rows": 2000},
        {"ticker": "SHORT", "sector_etf": "XLF", "price_rows": 100},
    ]).to_csv(audit, index=False)
    pd.DataFrame([{"ticker": "OLD"}]).to_csv(events, index=False)
    source = load_protocol()
    source["sample"]["minimum_tickers"] = 1
    source["sample"]["required_sector_count"] = 1
    protocol.write_text(json.dumps(source), encoding="utf-8")
    monkeypatch.setattr(
        "herd.rush_downside_asymmetry_universe_v1.verify_snapshot",
        lambda _: {
            "snapshot_id": "test",
            "snapshot_sha256": "abc",
            "files": {"OLD": {}, "NEW": {}, "SHORT": {}},
        },
    )
    rows, report = build_universe(audit, events, snapshot, protocol)
    assert rows["ticker"].tolist() == ["NEW"]
    assert report["ticker_overlap_count"] == 0
    assert report["status"] == "LOCKED_OOS_UNIVERSE"
