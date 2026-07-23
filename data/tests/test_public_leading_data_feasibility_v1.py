import json
from pathlib import Path

from herd.public_leading_data_feasibility_v1 import audit


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "data/herd/public_leading_data_feasibility_v1.json"


def test_no_public_source_is_falsely_promoted_to_primary(monkeypatch):
    monkeypatch.chdir(ROOT)
    report = audit(PROTOCOL)
    assert report["status"] == "NO_PUBLIC_SOURCE_READY_FOR_PRIMARY_OOS"
    assert report["ready_primary_sources"] == []
    assert report["new_direction_hypothesis_preregistered"] is False
    assert report["price_outcomes_opened"] is False


def test_finra_is_recent_lane_and_13f_is_slow_context(monkeypatch):
    monkeypatch.chdir(ROOT)
    report = audit(PROTOCOL)
    decisions = {
        row["source"]: row for row in report["source_decisions"]
    }
    finra = decisions["FINRA_EXCHANGE_LISTED_SHORT_INTEREST"]
    assert finra["status"] == "PROSPECTIVE_SHADOW_AND_RECENT_SENSITIVITY_ONLY"
    assert finra["history_years"] < 10
    assert finra["potential_non_overlapping_eras"] < 4
    assert finra["direction_hypothesis_allowed"] is False
    form13 = decisions["SEC_13F_INSTITUTIONAL_HOLDINGS"]
    assert form13["status"] == "SLOW_CONTEXT_ONLY"
    assert form13["history_years"] >= 10
    assert form13["potential_non_overlapping_eras"] >= 4
    assert form13["gate_checks"]["information_lag"] is False


def test_paid_surface_and_free_volume_proxy_are_blocked(monkeypatch):
    monkeypatch.chdir(ROOT)
    decisions = {
        row["source"]: row
        for row in audit(PROTOCOL)["source_decisions"]
    }
    assert (
        decisions["CBOE_EQUITY_OPTION_SURFACE"]["status"]
        == "BLOCKED_BY_PUBLIC_RESEARCH_TIER"
    )
    assert (
        decisions["CBOE_FREE_EQUITY_OPTION_VOLUME"]["status"]
        == "REJECTED_AS_INCOMPLETE_OPTION_SURFACE_PROXY"
    )


def test_operational_action_stays_blocked_in_materialized_report():
    report = json.loads(
        (ROOT / "data/reports/public_leading_data_feasibility_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["operational_action_authority"] is False
    assert report["operational_action_ratio"] == 0.0
    assert report["blind_holdout_access"] is False
