import json
from pathlib import Path

from herd.sec_time_valid_ticker_cik_ledger_v2 import (
    _mark_conflicts,
    _split_anchor_components,
    Anchor,
    canonical_symbol,
    extract_reported_symbols,
)


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "data/herd/sec_time_valid_ticker_cik_ledger_v2.json"
REPORT = ROOT / "data/reports/sec_time_valid_ticker_cik_ledger_v2.json"


def _protocol() -> dict:
    return json.loads(PROTOCOL.read_text(encoding="utf-8"))


def test_protocol_is_locked_before_interval_generation():
    protocol = _protocol()
    assert protocol["status"] == "LOCKED_BEFORE_INTERVAL_GENERATION"
    assert protocol["authority"]["price_outcomes_opened"] is False
    assert protocol["authority"]["direction_hypothesis_allowed"] is False
    assert protocol["authority"]["operational_action_ratio"] == 0.0


def test_protocol_forbids_current_ticker_backfill_and_transition_guessing():
    protocol = _protocol()
    forbidden = set(protocol["forbidden"])
    assert "BACKFILL_CURRENT_TICKER" in forbidden
    assert "INFER_A_TICKER_CHANGE_FROM_FORM345_ANCHORS_ALONE" in forbidden
    assert protocol["interval_policy"]["extrapolate_before_first_anchor"] is False
    assert protocol["interval_policy"]["extrapolate_after_last_anchor"] is False


def test_finra_remains_recent_shadow_only_even_if_identifier_gate_passes():
    protocol = _protocol()
    gate = protocol["finra_shadow_gate"]
    assert gate["allowed_if_passed"] == "PROSPECTIVE_SHADOW_OBSERVATION_ONLY"
    assert gate["primary_long_horizon_oos_allowed"] is False
    assert gate["required_time_valid_cik_link_coverage"] == 0.95


def test_sec_reported_symbol_parser_is_conservative_but_supports_share_classes():
    assert extract_reported_symbols("NYSE: GLW") == ["GLW"]
    assert extract_reported_symbols("BFA, BFB") == ["BFA", "BFB"]
    assert extract_reported_symbols("LEN, LEN.B") == ["LEN", "LEN.B"]
    assert extract_reported_symbols("-") == []
    assert extract_reported_symbols("fo9jod#z") == []
    assert canonical_symbol("BF-B") == "BFB"


def test_long_anchor_gap_splits_intervals():
    first = Anchor(
        "0000000001", "AAA", "AAA", __import__("datetime").date(2021, 1, 1),
        "a", "4", "2021Q1",
    )
    second = Anchor(
        "0000000001", "AAA", "AAA", __import__("datetime").date(2021, 2, 1),
        "b", "4", "2021Q1",
    )
    distant = Anchor(
        "0000000001", "AAA", "AAA", __import__("datetime").date(2023, 1, 1),
        "c", "4", "2023Q1",
    )
    assert _split_anchor_components([first, second, distant], 550) == [
        [first, second],
        [distant],
    ]


def test_overlapping_symbol_intervals_with_different_ciks_are_excluded():
    rows = [
        {
            "canonical_symbol": "AAA",
            "cik": "0000000001",
            "valid_from": "2022-01-01",
            "valid_to": "2022-12-31",
        },
        {
            "canonical_symbol": "AAA",
            "cik": "0000000002",
            "valid_from": "2022-06-01",
            "valid_to": "2023-01-01",
        },
    ]
    assert _mark_conflicts(rows) == 2
    assert {row["status"] for row in rows} == {"CONFLICT_EXCLUDED"}


def test_generated_ledger_keeps_all_model_authority_closed():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["status"] == "TIME_VALID_INTERVAL_LEDGER_BUILT"
    assert report["current_ticker_backfill_performed"] is False
    assert report["price_outcomes_opened"] is False
    assert report["direction_hypothesis_preregistered"] is False
    assert report["operational_action_ratio"] == 0.0
