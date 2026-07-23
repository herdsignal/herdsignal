import csv
import json

from herd.unified_pit_shadow_panel_v1 import (
    PANEL,
    PROTOCOL,
    REPORT,
    build,
)


def _rows(path=PANEL) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_protocol_is_source_fact_only():
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["status"] == "LOCKED_BEFORE_PANEL_BUILD"
    assert protocol["snapshot_policy"]["duplicate_full_source_history"] is False
    assert protocol["snapshot_policy"][
        "current_reference_identity_fallback_for_historical_dates"
    ] is False
    assert protocol["authority"]["source_fact"] is True
    assert protocol["authority"]["direction"] is False
    assert protocol["authority"]["veto"] is False
    assert protocol["authority"]["operational_action_ratio"] == 0.0


def test_panel_is_deterministic(tmp_path):
    generated = tmp_path / "panel.csv"
    report = build(panel_path=generated, report_path=tmp_path / "report.json")
    assert generated.read_bytes() == PANEL.read_bytes()
    assert report["panel_sha256"] == json.loads(
        REPORT.read_text(encoding="utf-8")
    )["panel_sha256"]


def test_panel_contains_three_distinct_public_fact_sources():
    rows = _rows()
    assert {row["source"] for row in rows} == {
        "FINRA_SHORT_INTEREST",
        "SEC_FORM4_CODE_P",
        "SEC_8K_GUIDANCE",
    }
    assert all(row["source_fact_authority"] == "True" for row in rows)
    assert all(row["direction_authority"] == "False" for row in rows)
    assert all(row["veto_authority"] == "False" for row in rows)


def test_panel_has_unique_ids_and_no_model_outputs():
    rows = _rows()
    assert len({row["panel_row_id"] for row in rows}) == len(rows)
    forbidden = {"future_return", "signal", "action", "label", "herd_score"}
    assert forbidden.isdisjoint(rows[0])
    assert all(row["feature_value"] for row in rows)


def test_finra_current_reference_fallback_never_backfills_history():
    rows = [
        row for row in _rows()
        if row["source"] == "FINRA_SHORT_INTEREST"
    ]
    assert len({row["ticker"] for row in rows}) == 503
    assert {
        json.loads(row["dimensions_json"])["settlement_date"]
        for row in rows
    } == {"2026-06-30"}
    assert {
        row["identity_confidence"] for row in rows
    } == {
        "TIME_VALID_SEC_CIK_EXACT",
        "CURRENT_REFERENCE_SNAPSHOT_CIK",
    }


def test_published_report_preserves_research_firewall():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["status"] == "HASH_LOCKED_PROSPECTIVE_SEED_SNAPSHOT_READY"
    assert report["full_source_history_duplicated"] is False
    assert report["price_or_return_outcomes_opened"] is False
    assert report["direction_labels_created"] is False
    assert report["veto_authority_granted"] is False
    assert report["primary_long_horizon_oos_allowed"] is False
    assert report["operational_action_ratio"] == 0.0
    assert report["finra_current_snapshot_coverage_gate"]["passed"] is True
    assert report["finra_current_snapshot_coverage_gate"][
        "historical_current_reference_backfill_performed"
    ] is False
    assert report["source_summaries"]["FINRA_SHORT_INTEREST"][
        "current_reference_ticker_coverage"
    ] >= 0.95
