import json
from pathlib import Path

from herd.sec_targeted_cover_corpus_v1 import (
    _validate_rows,
    sha256,
)


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "data/herd/sec_targeted_cover_ticker_cik_v1.json"
REPORT = ROOT / "data/reports/sec_targeted_cover_corpus_v1.json"
ANCHORS = ROOT / "data/reports/sec_targeted_cover_anchors_v1.csv"


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


def test_published_corpus_is_hash_locked_tagged_evidence_only():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["status"] == "HASH_LOCKED_TAGGED_COVER_ANCHORS_READY"
    assert report["filing_count"] == 396
    assert report["accepted_tagged_filing_count"] == 395
    assert report["anchor_count"] == 536
    assert report["anchors_sha256"] == sha256(ANCHORS)
    assert report["plain_text_regex_used_as_evidence"] is False
    assert report["current_ticker_backfill_performed"] is False


def test_published_corpus_contains_targeted_identity_edge_cases():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert set(report["canonical_symbols"]) == {
        "BK",
        "BLK",
        "BNY",
        "BRKA",
        "BRKB",
        "CRH",
        "GOOG",
        "GOOGL",
    }
    spans = {
        (row["canonical_symbol"], row["cik"]): row
        for row in report["anchor_spans"]
    }
    assert spans[("BLK", "0001364742")]["last_anchor_date"] < (
        spans[("BLK", "0002012383")]["first_anchor_date"]
    )
    assert spans[("BNY", "0001390777")]["first_anchor_date"] == "2026-06-12"
    assert spans[("BK", "0001390777")]["last_anchor_date"] == "2026-05-01"


def test_row_validator_rejects_allowlist_escape():
    protocol = _protocol()
    manifest = {
        "filing_count": 1,
        "filings_with_accepted_tagged_symbols": 1,
        "anchor_count": 1,
    }
    filing = {
        "cik": "0001390777",
        "accession_number": "a",
        "source_sha256": "h",
        "accepted_at": "2026-06-12T20:49:00.000Z",
        "form": "8-K",
        "evidence_status": "TAGGED_TARGET_SYMBOL_VERIFIED",
    }
    anchor = {
        "entity": "BNY_MELLON",
        "cik": "0001390777",
        "canonical_symbol": "WRONG",
        "reported_symbol": "WRONG",
        "filing_date": "2026-06-12",
        "accepted_at": filing["accepted_at"],
        "accession_number": "a",
        "form": "8-K",
        "source_sha256": "h",
    }
    assert _validate_rows(protocol, manifest, [filing], [anchor])[
        "all_rows_verified"
    ] is False
