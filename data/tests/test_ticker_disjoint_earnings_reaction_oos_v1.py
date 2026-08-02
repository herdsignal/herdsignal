import pandas as pd

from herd.ticker_disjoint_earnings_reaction_oos_v1 import (
    build_prospective_gate,
    collapse_quarterly_disclosures,
    reaction_sessions,
)


def test_collapse_keeps_first_disclosure_per_ticker_report_period():
    events = pd.DataFrame([
        {"event_id": "10q", "ticker": "AAA", "report_date": "2025-12-31", "accepted_at": "2026-02-03T20:00:00Z"},
        {"event_id": "8k", "ticker": "AAA", "report_date": "2025-12-31", "accepted_at": "2026-02-01T20:00:00Z"},
        {"event_id": "other", "ticker": "AAA", "report_date": "2026-03-31", "accepted_at": "2026-05-01T20:00:00Z"},
    ])
    assert collapse_quarterly_disclosures(events)["event_id"].tolist() == ["8k", "other"]


def test_reaction_window_includes_premarket_session_but_not_intraday_session():
    sessions = pd.date_range("2026-01-30", periods=7, freq="B")
    premarket = reaction_sessions(sessions, pd.Timestamp("2026-02-02T13:00:00Z"))
    after_open = reaction_sessions(sessions, pd.Timestamp("2026-02-02T16:00:00Z"))
    assert premarket == (0, 3)
    assert after_open == (1, 4)


def test_prospective_outcomes_are_fail_closed_until_history_passes():
    blocked = build_prospective_gate(False)
    active = build_prospective_gate(True)
    assert blocked["status"] == "PROSPECTIVE_COLLECTION_ONLY_CONFIRMATION_BLOCKED"
    assert blocked["sec_append_only_collection_active"] is True
    assert blocked["prospective_outcomes_may_be_opened_when_mature"] is False
    assert active["prospective_outcomes_may_be_opened_when_mature"] is True
    assert active["operational_action_ratio"] == 0.0
