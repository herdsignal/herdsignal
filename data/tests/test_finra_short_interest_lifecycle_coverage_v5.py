import csv
import json

from herd.finra_short_interest_lifecycle_coverage_v5 import (
    DETAIL,
    REPORT,
    audit_lifecycle_v5,
)


def _details() -> list[dict]:
    with DETAIL.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_lifecycle_coverage_gate_passes_all_required_cohorts(tmp_path):
    report = audit_lifecycle_v5(
        tmp_path / "report.json",
        tmp_path / "detail.csv",
    )
    assert report["finra_shadow_identifier_gate_passed"] is True
    assert all(
        row["lifecycle_identifier_gate_passed"]
        for row in report["cohorts"]
    )


def test_published_lifecycle_audit_keeps_calendar_and_identity_denominators():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["status"] == (
        "HASH_LOCKED_LIFECYCLE_IDENTIFIER_READY_FOR_SHADOW"
    )
    assert report["lifecycle_denominator_is_not_sec_interval_span"] is True
    assert report["first_finra_observation_used_as_sec_identity_proof"] is False
    assert report["primary_long_horizon_oos_allowed"] is False
    assert report["operational_action_ratio"] == 0.0
    assert report["decision"] == (
        "ALLOW_PROSPECTIVE_SHADOW_WITH_EXPLICIT_TARGET_BLOCKERS"
    )


def test_target_queue_reports_individual_source_exhaustion_blockers():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    audit = report["target_gap_audit"]
    assert audit["target_entity_count"] == 25
    assert audit["complete_target_count"] == 20
    assert audit["blocked_target_count"] == 5
    assert audit["all_target_identifiers_complete"] is False
    assert report["all_target_identifiers_complete"] is False
    assert {
        row["ticker"] for row in audit["blocked_targets"]
    } == {"APO", "CRH", "DHI", "DOV", "DOW"}
    assert {
        row["blocker"] for row in audit["blocked_targets"]
    } == {"PUBLIC_PRIMARY_ANCHOR_GAP_AFTER_SOURCE_EXHAUSTION"}
    assert audit["current_ticker_backfill_performed"] is False
    assert audit["unsupported_symbol_normalization_performed"] is False
    assert audit["source_exhaustion_is_not_treated_as_identity_proof"] is True


def test_ticker_collision_rows_use_issue_identity_filters():
    rows = {
        (row["cohort"], row["ticker"]): row for row in _details()
    }
    current = "CURRENT_SP500_REFERENCE_503"
    assert rows[(current, "DOC")]["observation_ticker"] == "PEAK|DOC"
    assert rows[(current, "COR")]["observation_ticker"] == "ABC|COR"
    assert rows[(current, "META")]["observation_ticker"] == "FB|META"
    assert rows[(current, "ECHO")]["observation_ticker"] == "SATS|ECHO"
    assert all(
        rows[(current, ticker)]["identity_issue_name_regex"]
        for ticker in ("DOC", "COR", "META", "ECHO", "COHR")
    )
