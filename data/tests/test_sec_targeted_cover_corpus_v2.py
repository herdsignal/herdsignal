import csv
import json

import pytest

from herd.sec_targeted_cover_corpus_v2 import (
    CATALOG,
    PROTOCOL,
    REPORT,
    SecTargetedCoverV2Error,
    _target_by_cik,
    _verify_protocol,
    extract_tagged_trading_symbols,
    submission_rows,
)


def test_v2_protocol_is_locked_and_outcome_closed():
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    queue_protocol, queue = _verify_protocol(protocol)
    assert protocol["status"] == "LOCKED_BEFORE_PRIMARY_SOURCE_COLLECTION"
    assert len(queue) == 25
    assert "6-K" in queue_protocol["collection_policy"]["eligible_forms"]
    assert protocol["authority"]["price_outcomes_opened"] is False
    assert protocol["authority"]["operational_action_ratio"] == 0.0


def test_target_map_preserves_successor_and_predecessor_ciks():
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    _, queue = _verify_protocol(protocol)
    targets = _target_by_cik(queue)
    assert len(targets) == 26
    assert targets["0001144519"]["reference_ticker"] == "BG"
    assert targets["0001996862"]["reference_ticker"] == "BG"


def test_only_structured_trading_symbol_tags_are_extracted():
    content = b"""
    <html><body>
      <ix:nonnumeric name="dei:TradingSymbol">FOX</ix:nonnumeric>
      <ix:nonnumeric name="dei:TradingSymbol">FOXA</ix:nonnumeric>
      <p>Trading Symbol FAKE</p>
    </body></html>
    """
    assert extract_tagged_trading_symbols(content) == ["FOX", "FOXA"]
    assert extract_tagged_trading_symbols(
        b"<html><p>Trading Symbol FAKE</p></html>"
    ) == []


def test_submission_rows_reject_incomplete_columns():
    payload = {
        "filings": {
            "recent": {
                "accessionNumber": ["0000000000-24-000001"],
                "filingDate": ["2024-01-01"],
                "acceptanceDateTime": [],
                "form": ["10-K"],
                "primaryDocument": ["a.htm"],
            }
        }
    }
    with pytest.raises(SecTargetedCoverV2Error):
        submission_rows(payload)


def test_numeric_volume_is_estimate_not_completion_gate():
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    gate = protocol["completion_gate"]
    assert gate["estimate_is_not_a_pass_threshold"] is True
    assert gate["all_discovered_eligible_filings_must_be_downloaded"] is True
    assert gate["unresolved_download_failures_allowed"] == 0


def test_published_v2_corpus_exhausted_all_discovered_sources():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["status"] == "HASH_LOCKED_ELIGIBLE_SOURCE_EXHAUSTED"
    assert report["target_entity_count"] == 25
    assert report["target_cik_count"] == 26
    assert report["filing_count"] == 3569
    assert report["anchor_count"] == 4455
    assert report["unresolved_failures"] == 0
    assert report["all_artifacts_verified"] is True
    assert report["price_outcomes_opened"] is False


def test_every_collection_cik_has_accepted_primary_cover_evidence():
    with CATALOG.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    accepted_ciks = {
        row["cik"] for row in rows
        if row["evidence_status"] == "TAGGED_TARGET_SYMBOL_VERIFIED"
    }
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    _, queue = _verify_protocol(protocol)
    expected_ciks = {
        cik
        for row in queue
        for cik in row["collection_ciks"].split("|")
    }
    assert accepted_ciks == expected_ciks
    assert len({row["accession_number"] for row in rows}) == len(rows)
