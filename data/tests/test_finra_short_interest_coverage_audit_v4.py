import csv
import json
from pathlib import Path

from herd.finra_short_interest_coverage_audit_v4 import load_sec_intervals


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "data/reports/finra_short_interest_coverage_audit_v4.json"
DETAIL = ROOT / "data/reports/finra_short_interest_ticker_coverage_v4.csv"


def test_v4_interval_lineage_is_hash_verified():
    intervals, lineage = load_sec_intervals()
    assert len(intervals) == lineage["verified_interval_count"]
    assert lineage["targeted_filing_count"] == 396
    assert lineage["targeted_anchor_count"] == 536
    assert lineage["targeted_entity_count"] == 5
    assert lineage["full_universe_rescan_performed"] is False


def test_v4_gate_passes_without_opening_model_authority():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    cohorts = {row["cohort"]: row for row in report["cohorts"]}
    assert cohorts["ORIGINAL_RESEARCH_51"]["pit_identifier_gate_passed"] is True
    assert (
        cohorts["INDEPENDENT_ELIGIBLE_388"]["pit_identifier_gate_passed"]
        is True
    )
    assert report["finra_shadow_identifier_gate_passed"] is True
    assert report["decision"] == "ALLOW_PROSPECTIVE_SHADOW_OBSERVATION_ONLY"
    assert report["primary_long_horizon_oos_allowed"] is False
    assert report["new_direction_hypothesis_preregistered"] is False
    assert report["price_outcomes_opened"] is False
    assert report["herd_formula_change_allowed"] is False
    assert report["operational_action_authority"] is False
    assert report["operational_action_ratio"] == 0.0


def test_bny_identity_uses_bk_then_bny_and_filters_issue_name():
    with DETAIL.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    row = next(
        item for item in rows
        if item["cohort"] == "INDEPENDENT_ELIGIBLE_388"
        and item["ticker"] == "BNY"
    )
    assert row["observation_ticker"] == "BK|BNY"
    assert row["cohort_symbol_overridden"] == "True"
    assert row["finra_symbols_observed"] == "BK|BNY"
    assert row["identity_issue_name_regex"] == "^BANK OF NEW YORK MELLON"
    assert float(row["time_valid_cik_link_coverage"]) > 0.95


def test_historical_unrelated_bny_is_never_assigned():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    ledger = report["identifier_ledger"]
    assert ledger["bny_issue_name_filter_required"] is True
    assert ledger["historical_unrelated_bny_assigned"] is False
    assert ledger["cohort_reference_cik_backfill_performed"] is False
