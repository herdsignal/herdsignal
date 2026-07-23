import json
from pathlib import Path

from herd.finra_short_interest_coverage_audit_v1 import (
    _canonical_symbol,
    _cohorts,
    _date_in_interval,
    _verified_intervals,
)


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "data/herd/finra_short_interest_immutable_census_v1.json"
REPORT = ROOT / "data/reports/finra_short_interest_coverage_audit_v1.json"


def _protocol() -> dict:
    return json.loads(PROTOCOL.read_text(encoding="utf-8"))


def test_symbol_normalization_only_removes_verified_format_punctuation():
    assert _canonical_symbol("BRK-B") == "BRKB"
    assert _canonical_symbol("BRK.B") == "BRKB"
    assert _canonical_symbol("BF/B") == "BFB"
    assert _canonical_symbol("META") == "META"


def test_locked_cohorts_have_expected_sizes():
    cohorts = _cohorts(_protocol())
    assert len(cohorts["ORIGINAL_RESEARCH_51"]) == 51
    assert len(cohorts["INDEPENDENT_ELIGIBLE_388"]) == 388
    assert len(cohorts["CURRENT_SP500_REFERENCE_503"]) == 503


def test_only_explicitly_verified_intervals_are_loaded():
    intervals = _verified_intervals(_protocol())
    assert intervals
    assert all(item["cik"].isdigit() and len(item["cik"]) == 10 for item in intervals)
    assert {item["source"] for item in intervals} == {
        "PRICE_UNIVERSE_CIK_PERIODS",
        "VERIFIED_TICKER_ALIAS_LEDGER",
    }


def test_interval_boundaries_are_inclusive_and_open_end_is_supported():
    closed = {"valid_from": "2021-01-01", "valid_to": "2021-12-31"}
    opened = {"valid_from": "2022-01-01", "valid_to": None}
    assert _date_in_interval("2021-01-01", closed)
    assert _date_in_interval("2021-12-31", closed)
    assert not _date_in_interval("2022-01-01", closed)
    assert _date_in_interval("2026-07-23", opened)


def test_generated_audit_verifies_corpus_but_keeps_pit_identifier_gate_closed():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["status"] == "HASH_LOCKED_PIT_IDENTIFIER_INCOMPLETE"
    assert report["corpus"]["file_count"] == 122
    assert report["corpus"]["settlement_date_count"] == 122
    assert report["integrity"]["all_raw_hashes_verified"] is True
    assert all(
        cohort["ticker_ever_observed_coverage"] == 1.0
        for cohort in report["cohorts"]
    )
    assert not all(
        cohort["pit_identifier_gate_passed"]
        for cohort in report["cohorts"]
    )
    assert report["price_outcomes_opened"] is False
    assert report["new_direction_hypothesis_preregistered"] is False
    assert report["operational_action_ratio"] == 0.0
