import json
from pathlib import Path

from herd.sec_cover_page_targeted_source_v1 import (
    _filing_rows,
    extract_entity_ciks,
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
