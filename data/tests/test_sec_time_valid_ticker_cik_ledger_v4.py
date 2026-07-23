import csv
import json
from pathlib import Path

from herd.sec_time_valid_ticker_cik_ledger_v4 import (
    _merge_same_identity,
)


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "data/herd/sec_time_valid_ticker_cik_ledger_v4.json"
LEDGER = ROOT / "data/reports/sec_time_valid_ticker_cik_intervals_v4.csv"
REPORT = ROOT / "data/reports/sec_time_valid_ticker_cik_ledger_v4.json"


def _rows() -> list[dict]:
    with LEDGER.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_v4_protocol_forbids_extrapolation_and_model_use():
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["status"] == "LOCKED_BEFORE_INTERVAL_GENERATION"
    assert protocol["interval_policy"][
        "extrapolate_before_first_primary_cover_anchor"
    ] is False
    assert protocol["interval_policy"][
        "extrapolate_after_last_primary_cover_anchor"
    ] is False
    assert protocol["authority"]["price_outcomes_opened"] is False
    assert protocol["authority"]["operational_action_ratio"] == 0.0


def test_merge_only_joins_overlapping_or_adjacent_same_identity():
    template = {
        "canonical_symbol": "AAA",
        "reported_symbols": "AAA",
        "cik": "0000000001",
        "anchor_count": 2,
        "first_accession": "a",
        "last_accession": "b",
        "source_quarters": "A",
        "anchor_sha256": "a",
        "boundary_sources": "A",
        "status": "CANDIDATE",
    }
    rows = [
        {**template, "valid_from": "2022-01-01", "valid_to": "2022-01-10"},
        {**template, "valid_from": "2022-01-11", "valid_to": "2022-01-20"},
        {**template, "valid_from": "2022-01-22", "valid_to": "2022-01-30"},
    ]
    merged = _merge_same_identity(rows)
    assert [(row["valid_from"], row["valid_to"]) for row in merged] == [
        ("2022-01-01", "2022-01-20"),
        ("2022-01-22", "2022-01-30"),
    ]


def test_v4_preserves_bny_and_blk_time_boundaries():
    rows = [
        row for row in _rows()
        if row["status"] == "TIME_VALID_CIK_VERIFIED"
    ]
    bk = [row for row in rows if row["canonical_symbol"] == "BK"]
    bny = [row for row in rows if row["canonical_symbol"] == "BNY"]
    assert any(
        row["cik"] == "0001390777" and row["valid_to"] == "2026-05-01"
        for row in bk
    )
    assert any(
        row["cik"] == "0001390777" and row["valid_from"] == "2026-06-12"
        for row in bny
    )
    blk = [row for row in rows if row["canonical_symbol"] == "BLK"]
    assert {row["cik"] for row in blk} == {"0001364742", "0002012383"}
    assert max(
        row["valid_to"] for row in blk if row["cik"] == "0001364742"
    ) < min(
        row["valid_from"] for row in blk if row["cik"] == "0002012383"
    )


def test_v4_keeps_dual_classes_and_authority_closed():
    rows = _rows()
    verified_symbols = {
        row["canonical_symbol"]
        for row in rows
        if row["status"] == "TIME_VALID_CIK_VERIFIED"
    }
    assert {"BRKA", "BRKB", "GOOG", "GOOGL"}.issubset(verified_symbols)
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["status"] == "TIME_VALID_TARGETED_COVER_LEDGER_BUILT"
    assert report["edge_case_audit"]["blk_different_cik_overlap"] is False
    assert report["current_ticker_backfill_performed"] is False
    assert report["direction_hypothesis_preregistered"] is False
    assert report["operational_action_ratio"] == 0.0
