import json
from pathlib import Path

from herd.finra_short_interest_coverage_audit_v2 import load_sec_intervals


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "data/reports/finra_short_interest_coverage_audit_v2.json"


def test_sec_interval_lineage_and_rows_are_hash_verified():
    intervals, lineage = load_sec_intervals()
    assert len(intervals) == lineage["verified_interval_count"]
    assert intervals
    assert all(len(row["cik"]) == 10 and row["cik"].isdigit() for row in intervals)
    assert lineage["current_ticker_backfill_performed"] is False


def test_finra_v2_never_opens_model_or_action_authority():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["report_version"] == "FINRA_SHORT_INTEREST_COVERAGE_AUDIT_V2"
    assert report["primary_long_horizon_oos_allowed"] is False
    assert report["new_direction_hypothesis_preregistered"] is False
    assert report["price_outcomes_opened"] is False
    assert report["herd_formula_change_allowed"] is False
    assert report["operational_action_authority"] is False
    assert report["operational_action_ratio"] == 0.0


def test_v2_requires_a_unique_time_valid_cik_instead_of_current_cik_backfill():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    ledger = report["identifier_ledger"]
    assert ledger["strict_reference_cik_required"] is False
    assert ledger["cohort_reference_cik_backfill_performed"] is False
    assert ledger["unique_matching_cik_required_per_date"] is True


def test_v2_expands_identity_coverage_but_keeps_strict_gate_closed():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    cohorts = {row["cohort"]: row for row in report["cohorts"]}
    assert cohorts["ORIGINAL_RESEARCH_51"]["time_valid_cik_link_coverage"] > 0.95
    assert cohorts["INDEPENDENT_ELIGIBLE_388"]["time_valid_cik_link_coverage"] > 0.94
    assert (
        cohorts["INDEPENDENT_ELIGIBLE_388"]["pit_identifier_gate_passed"]
        is False
    )
    assert report["finra_shadow_identifier_gate_passed"] is False
    assert report["status"] == "HASH_LOCKED_PIT_IDENTIFIER_INCOMPLETE"
