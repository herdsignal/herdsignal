import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "data/herd/sec_time_valid_ticker_cik_ledger_v2.json"


def _protocol() -> dict:
    return json.loads(PROTOCOL.read_text(encoding="utf-8"))


def test_protocol_is_locked_before_interval_generation():
    protocol = _protocol()
    assert protocol["status"] == "LOCKED_BEFORE_INTERVAL_GENERATION"
    assert protocol["authority"]["price_outcomes_opened"] is False
    assert protocol["authority"]["direction_hypothesis_allowed"] is False
    assert protocol["authority"]["operational_action_ratio"] == 0.0


def test_protocol_forbids_current_ticker_backfill_and_transition_guessing():
    protocol = _protocol()
    forbidden = set(protocol["forbidden"])
    assert "BACKFILL_CURRENT_TICKER" in forbidden
    assert "INFER_A_TICKER_CHANGE_FROM_FORM345_ANCHORS_ALONE" in forbidden
    assert protocol["interval_policy"]["extrapolate_before_first_anchor"] is False
    assert protocol["interval_policy"]["extrapolate_after_last_anchor"] is False


def test_finra_remains_recent_shadow_only_even_if_identifier_gate_passes():
    protocol = _protocol()
    gate = protocol["finra_shadow_gate"]
    assert gate["allowed_if_passed"] == "PROSPECTIVE_SHADOW_OBSERVATION_ONLY"
    assert gate["primary_long_horizon_oos_allowed"] is False
    assert gate["required_time_valid_cik_link_coverage"] == 0.95
