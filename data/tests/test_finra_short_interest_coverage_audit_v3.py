import csv
import json
from pathlib import Path

from herd.finra_short_interest_coverage_audit_v1 import _observation_symbol
from herd.finra_short_interest_coverage_audit_v3 import load_sec_intervals


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "data/reports/finra_short_interest_coverage_audit_v3.json"
DETAIL = ROOT / "data/reports/finra_short_interest_ticker_coverage_v3.csv"


def test_cohort_symbol_override_is_explicit_and_narrow():
    overrides = {"BNY": "BK"}
    assert _observation_symbol("BNY", overrides) == "BK"
    assert _observation_symbol("BLK", overrides) == "BLK"


def test_v3_interval_lineage_is_hash_verified():
    intervals, lineage = load_sec_intervals()
    assert len(intervals) == lineage["verified_interval_count"]
    assert lineage["targeted_document_count"] == 113
    assert lineage["targeted_anchor_count"] == 133
    assert lineage["full_universe_rescan_performed"] is False
    assert lineage["bny_linked_to_bny_mellon_cik"] is False


def test_v3_gate_passes_without_opening_model_authority():
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


def test_bny_row_uses_bk_observation_without_assigning_finra_bny():
    with DETAIL.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    row = next(
        item for item in rows
        if item["cohort"] == "INDEPENDENT_ELIGIBLE_388"
        and item["ticker"] == "BNY"
    )
    assert row["observation_ticker"] == "BK"
    assert row["cohort_symbol_overridden"] == "True"
    assert row["finra_symbols_observed"] == "BK"
    assert row["link_status"] == "PARTIAL_TIME_VALID_CIK"
    assert float(row["time_valid_cik_link_coverage"]) > 0.95
