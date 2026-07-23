import json
from pathlib import Path

from herd.sec_cover_page_targeted_source_v1 import (
    _filing_rows,
    extract_entity_ciks,
)
from herd.sec_cover_page_targeted_ledger_v1 import (
    _mark_conflicts,
    build_targeted_intervals,
)


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "data/herd/sec_cover_page_targeted_ledger_v1.json"


def _protocol() -> dict:
    return json.loads(PROTOCOL.read_text(encoding="utf-8"))


def test_targeted_protocol_is_locked_and_forbids_full_rescan():
    protocol = _protocol()
    assert protocol["status"] == "LOCKED_BEFORE_SOURCE_COLLECTION"
    assert protocol["selection_policy"]["full_universe_rescan_forbidden"] is True
    assert "COLLECT_ALL_503_ISSUERS" in protocol["forbidden"]


def test_bny_is_corrected_to_bk_and_never_backfilled_as_bny():
    protocol = _protocol()
    assert protocol["finra_v3_policy"]["cohort_symbol_overrides"] == {"BNY": "BK"}
    bny = next(
        row for row in protocol["targets"] if row["research_ticker"] == "BNY"
    )
    assert bny["resolved_ticker"] == "BK"
    assert bny["expected_cover_symbols"] == ["BK"]
    assert "LINK_FINRA_BNY_TO_BNY_MELLON" in protocol["forbidden"]


def test_blackrock_predecessor_and_successor_are_bounded_exactly():
    targets = [
        row for row in _protocol()["targets"] if row["research_ticker"] == "BLK"
    ]
    assert {(row["cik"], row.get("valid_from"), row.get("valid_to")) for row in targets} == {
        ("0001364742", None, "2024-09-30"),
        ("0002012383", "2024-10-01", None),
    }


def test_model_and_action_authority_remain_closed():
    authority = _protocol()["authority"]
    assert authority["price_outcomes_opened"] is False
    assert authority["direction_hypothesis_allowed"] is False
    assert authority["herd_formula_change_allowed"] is False
    assert authority["operational_action_ratio"] == 0.0


def test_inline_xbrl_entity_cik_is_extracted():
    content = (
        b'<ix:nonNumeric name="dei:EntityCentralIndexKey">'
        b"0001652044</ix:nonNumeric>"
    )
    assert extract_entity_ciks(content) == ["0001652044"]


def test_submission_rows_require_acceptance_datetime_alignment():
    rows = _filing_rows({
        "accessionNumber": ["0001"],
        "filingDate": ["2025-01-01"],
        "acceptanceDateTime": ["2025-01-01T16:30:00.000Z"],
        "form": ["10-K"],
        "primaryDocument": ["report.htm"],
    })
    assert rows[0]["accepted_at"] == "2025-01-01T16:30:00.000Z"


def test_targeted_intervals_apply_exact_blackrock_cik_boundary():
    protocol = _protocol()
    source = {
        "accepted_anchors": [
            {
                "cik": "0001364742",
                "symbol": "BLK",
                "canonical_symbol": "BLK",
                "filing_date": day,
                "accepted_at": f"{day}T16:00:00Z",
                "accession_number": f"old-{position}",
                "form": "10-Q",
                "document_sha256": str(position) * 64,
            }
            for position, day in enumerate(("2024-02-01", "2024-08-01"), start=1)
        ] + [
            {
                "cik": "0002012383",
                "symbol": "BLK",
                "canonical_symbol": "BLK",
                "filing_date": day,
                "accepted_at": f"{day}T16:00:00Z",
                "accession_number": f"new-{position}",
                "form": "10-Q",
                "document_sha256": str(position + 2) * 64,
            }
            for position, day in enumerate(("2024-11-01", "2025-02-01"), start=1)
        ],
        "identity_events": [{
            **protocol["exact_identity_events"][0],
            "required_terms_verified": True,
        }],
    }
    intervals = [
        row for row in build_targeted_intervals(protocol, source)
        if row["canonical_symbol"] == "BLK"
    ]
    assert {
        (row["cik"], row["valid_from"], row["valid_to"])
        for row in intervals
    } == {
        ("0001364742", "2024-02-01", "2024-09-30"),
        ("0002012383", "2024-10-01", "2025-02-01"),
    }
    assert _mark_conflicts(intervals) == 0


def test_generated_targeted_ledger_is_hash_locked_and_non_operational():
    report_path = ROOT / "data/reports/sec_cover_page_targeted_ledger_v1.json"
    if not report_path.exists():
        return
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["targeted_document_count"] == 113
    assert report["targeted_anchor_count"] == 133
    assert report["conflict_excluded_interval_count"] == 0
    assert report["cohort_symbol_overrides"] == {"BNY": "BK"}
    assert report["bny_linked_to_bny_mellon_cik"] is False
    assert report["blackrock_exact_transition_applied"] is True
    assert report["operational_action_authority"] is False
    assert report["operational_action_ratio"] == 0.0
