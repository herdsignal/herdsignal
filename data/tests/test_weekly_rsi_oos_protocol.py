import json
from pathlib import Path


PROTOCOL = Path(__file__).parents[1] / "herd" / "weekly_rsi_oos_protocol_v1.json"


def test_weekly_rsi_oos_protocol_is_sparse_and_locked():
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["status"] == "LOCKED_BEFORE_OOS_RESULTS"
    assert protocol["outcome"]["primary_horizon_weeks"] == 13
    assert protocol["adoption_gate"]["maximum_extreme_entries_per_ticker_year"] == 2.0
    assert protocol["frequency_policy"]["all_actions_per_ticker_year_must_remain_at_or_below"] == 5.0


def test_oos_protocol_does_not_allow_high_rsi_alone_to_authorize_action():
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert len(protocol["hypotheses"]) == 4
    assert "AUTHORIZE_PROFIT_TAKE_BEFORE_INDEPENDENT_OOS_PASS" in protocol["forbidden"]
    assert protocol["matching"]["test_outcome_not_used_for_matching"] is True
