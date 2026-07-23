import csv
import json

from herd.sec_time_valid_ticker_cik_ledger_v5 import (
    LEDGER,
    PROTOCOL,
    REPORT,
    generate,
    sha256,
)


def _rows() -> list[dict]:
    with LEDGER.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_v5_protocol_locks_lifecycle_identity_boundaries():
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["status"] == "LOCKED_BEFORE_LIFECYCLE_LEDGER_GENERATION"
    assert protocol["authority"]["price_outcomes_opened"] is False
    assert protocol["authority"]["operational_action_ratio"] == 0.0
    assert protocol["finra_identity_aliases"]["DOC"]["symbols"] == [
        "PEAK",
        "DOC",
    ]
    assert protocol["finra_identity_aliases"]["META"]["symbols"] == [
        "FB",
        "META",
    ]
    assert protocol["lifecycle_coverage_policy"][
        "target_queue_requires_individual_coverage"
    ] is True
    assert any(
        row["role"] == "IDENTIFIER_GAP_QUEUE"
        for row in protocol["locked_inputs"]
    )


def test_v5_ledger_is_deterministic_and_hash_locked(tmp_path):
    ledger = tmp_path / "ledger.csv"
    report_path = tmp_path / "report.json"
    report = generate(ledger_path=ledger, report_path=report_path)
    assert report["ledger_sha256"] == sha256(ledger)
    assert ledger.read_bytes() == LEDGER.read_bytes()


def test_v5_preserves_edge_case_nonoverlap():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["status"] == "TIME_VALID_LIFECYCLE_LEDGER_BUILT"
    assert report["conflict_excluded_interval_count"] == 0
    assert all(report["edge_case_audit"].values())
    assert report["current_ticker_backfill_performed"] is False
    assert report["interval_extrapolation_performed"] is False


def test_cohr_predecessor_is_cut_before_successor_common_symbol():
    rows = [
        row for row in _rows()
        if row["cik"] == "0000820318"
        and row["canonical_symbol"] in {"IIVI", "COHR"}
        and row["status"] == "TIME_VALID_CIK_VERIFIED"
    ]
    iivi = [row for row in rows if row["canonical_symbol"] == "IIVI"]
    cohr = [row for row in rows if row["canonical_symbol"] == "COHR"]
    assert iivi and cohr
    assert max(row["valid_to"] for row in iivi) < min(
        row["valid_from"] for row in cohr
    )
