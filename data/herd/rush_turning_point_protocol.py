"""Rush 전환점 사건 연구의 사전등록 계약을 검증한다."""

from __future__ import annotations

import json
from pathlib import Path

from herd.timing_hypothesis_registry import registry_sha256

PROTOCOL_PATH = Path(__file__).with_name("rush_turning_point_protocol.json")
EXPECTED_STATES = {
    "HEALTHY_RUSH",
    "EXTENDING_RUSH",
    "EXHAUSTED_RUSH",
    "BREAKING_RUSH",
}


class RushTurningPointProtocolError(ValueError):
    pass


def validate_protocol(protocol: dict) -> dict:
    observation = protocol.get("observation", {})
    eligibility = protocol.get("rush_eligibility", {})
    contrast = protocol.get("primary_contrast", {})
    gate = protocol.get("adoption_gate", {})
    forbidden = set(protocol.get("forbidden", []))
    state_rules = protocol.get("state_rules", {})

    if protocol.get("status") != "LOCKED_BEFORE_OOS_RESULTS":
        raise RushTurningPointProtocolError("protocol must be locked")
    if (
        observation.get("signal_frequency") != "MONTH_END"
        or observation.get("forward_horizons_months") != [1, 3, 6]
        or observation.get("event_sampling")
        != "FIRST_MONTH_OF_STATE_TRANSITION"
        or "NON_OVERLAPPING" not in observation.get("inference_sample", "")
    ):
        raise RushTurningPointProtocolError("invalid event observation contract")
    if (
        eligibility.get("price_extension_score_minimum") != 75
        or eligibility.get("slow_trend_12m_return_minimum") != 0.0
    ):
        raise RushTurningPointProtocolError("Rush eligibility changed")
    if set(state_rules) != EXPECTED_STATES:
        raise RushTurningPointProtocolError("Rush lifecycle is incomplete")
    exhausted = set(state_rules["EXHAUSTED_RUSH"])
    if {
        "FAST_SLOW_GAP_LT_ZERO",
        "FAST_SLOW_GAP_1M_CHANGE_LT_ZERO",
        "PARTICIPATION_3M_CHANGE_LT_ZERO",
        "RELATIVE_FAST_SLOW_GAP_LT_ZERO",
    } - exhausted:
        raise RushTurningPointProtocolError(
            "exhaustion requires trend, participation and relative rollover"
        )
    if (
        set(contrast.get("treatment_states", []))
        != {"EXHAUSTED_RUSH", "BREAKING_RUSH"}
        or set(contrast.get("control_states", []))
        != {"HEALTHY_RUSH", "EXTENDING_RUSH"}
        or set(contrast.get("outcomes", []))
        != {"FORWARD_TOTAL_RETURN", "FORWARD_TROUGH_RETURN"}
    ):
        raise RushTurningPointProtocolError("primary contrast changed")
    if (
        gate.get("primary_horizon_months") != 3
        or gate.get("minimum_events_per_side", 0) < 30
        or gate.get("minimum_test_folds_per_side", 0) < 4
        or gate.get("minimum_directional_folds", 0) < 4
        or gate.get("maximum_holm_p_value", 1) > 0.1
        or gate.get("required_primary_outcomes") != 2
    ):
        raise RushTurningPointProtocolError("adoption gate is too weak")
    if {
        "HIGH_HERD_ALONE_AS_SELL_SIGNAL",
        "THRESHOLD_SEARCH_AFTER_RESULTS",
        "PARTIAL_PROFIT_TAKE_BEFORE_EVENT_GATE_PASS",
        "REENTRY_RULE_BEFORE_PROFIT_TAKE_GATE_PASS",
    } - forbidden:
        raise RushTurningPointProtocolError("unsafe shortcut is not forbidden")
    return {
        "protocol_version": protocol["protocol_version"],
        "status": protocol["status"],
        "state_count": len(state_rules),
        "sha256": registry_sha256(protocol),
    }


def load_protocol(path: Path = PROTOCOL_PATH) -> tuple[dict, dict]:
    protocol = json.loads(Path(path).read_text(encoding="utf-8"))
    return protocol, validate_protocol(protocol)


if __name__ == "__main__":
    _, audit = load_protocol()
    print(json.dumps(audit, ensure_ascii=False, indent=2))
