import csv
import json
from pathlib import Path

from herd.sec_identifier_gap_queue_v1 import (
    PROTOCOL,
    QUEUE,
    REPORT,
    build_queue,
    sha256,
)


ROOT = Path(__file__).resolve().parents[2]


def _rows() -> list[dict]:
    with QUEUE.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_gap_queue_protocol_is_locked_without_outcomes():
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["status"] == "LOCKED_BEFORE_TARGETED_COLLECTION_V2"
    assert protocol["selection"]["target_entity_count"] == 25
    assert protocol["selection"]["price_or_return_outcomes_used"] is False
    assert protocol["authority"]["future_return_labels_allowed"] is False
    assert protocol["authority"]["operational_action_ratio"] == 0.0


def test_gap_queue_is_deterministic_and_hash_locked(tmp_path):
    output = tmp_path / "queue.csv"
    report_path = tmp_path / "report.json"
    report = build_queue(queue_path=output, report_path=report_path)
    assert report["target_entity_count"] == 25
    assert report["unresolved_observed_ticker_dates"] == 682
    assert report["queue_sha256"] == sha256(output)
    assert output.read_bytes() == QUEUE.read_bytes()


def test_largest_unique_cik_gaps_are_selected():
    rows = _rows()
    assert rows[0]["reference_ticker"] == "FOXA"
    assert rows[1]["reference_ticker"] == "NWSA"
    assert len(rows) == 25
    assert len({row["reference_cik"] for row in rows}) == 25
    assert all(row["selected_without_price_outcomes"] == "True" for row in rows)


def test_identity_edge_cases_have_explicit_routes():
    by_ticker = {row["reference_ticker"]: row for row in _rows()}
    assert by_ticker["FOXA"]["accepted_symbols"] == "FOX|FOXA"
    assert by_ticker["NWSA"]["accepted_symbols"] == "NWS|NWSA"
    assert by_ticker["DOC"]["classification"] == (
        "TICKER_REUSE_AND_CURRENT_ISSUER_RENAME"
    )
    assert by_ticker["BG"]["collection_ciks"] == "0001144519|0001996862"
    assert by_ticker["CRH"]["classification"] == "FOREIGN_ISSUER_COVER_GAP"
    assert by_ticker["META"]["accepted_symbols"] == "FB|META"
    assert by_ticker["APO"]["accepted_symbols"] == "APO"
    assert by_ticker["IP"]["accepted_symbols"] == "IP"


def test_report_keeps_lifecycle_adjustment_for_later_stage():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["status"] == "HASH_LOCKED_TARGET_QUEUE_READY"
    assert report["raw_denominator_is_not_lifecycle_adjusted"] is True
    assert report["price_outcomes_opened"] is False
    assert report["direction_hypothesis_preregistered"] is False
