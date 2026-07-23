import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "data/herd/sec_targeted_cover_ticker_cik_v1.json"


def _protocol() -> dict:
    return json.loads(PROTOCOL.read_text(encoding="utf-8"))


def test_targeted_cover_protocol_is_locked_without_price_outcomes():
    protocol = _protocol()
    assert protocol["status"] == "LOCKED_BEFORE_TARGETED_COLLECTION"
    assert protocol["selection_policy"]["selected_without_price_outcomes"] is True
    assert protocol["selection_policy"]["full_universe_recollection_forbidden"] is True
    assert protocol["authority"]["price_outcomes_opened"] is False
    assert protocol["authority"]["operational_action_ratio"] == 0.0


def test_only_tagged_cover_symbols_can_become_evidence():
    policy = _protocol()["document_policy"]
    assert policy["accept_tagged_trading_symbol_only"] is True
    assert policy["plain_text_regex_symbol_is_evidence"] is False
    assert policy["current_submissions_ticker_array_is_evidence"] is False


def test_bny_ticker_reuse_and_foreign_issuer_are_explicitly_guarded():
    targets = {row["entity"]: row for row in _protocol()["targets"]}
    assert targets["BNY_MELLON"]["finra_issue_name_required_regex"].startswith("^BANK")
    assert targets["CRH"]["foreign_issuer_forms_required"] is True
    assert {"20-F", "20-F/A"}.issubset(_protocol()["eligible_forms"])


def test_targeted_intervals_never_extrapolate_outside_primary_anchors():
    policy = _protocol()["interval_policy"]
    assert policy["minimum_distinct_accessions"] == 2
    assert policy["extrapolate_before_first_anchor"] is False
    assert policy["extrapolate_after_last_anchor"] is False
    assert policy["same_symbol_overlapping_multiple_ciks_is_conflict"] is True
