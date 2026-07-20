"""SEC PIT 기업 상태 veto의 사전등록 계약을 검증한다."""

from __future__ import annotations

import json
from pathlib import Path

from herd.timing_hypothesis_registry import registry_sha256

PROTOCOL_PATH = Path(__file__).with_name("business_guard_protocol.json")


class BusinessGuardProtocolError(ValueError):
    pass


def validate_protocol(protocol: dict) -> dict:
    data = protocol.get("data_contract", {})
    features = protocol.get("features", {})
    guard = protocol.get("guard_rule", {})
    test = protocol.get("predictive_test", {})
    gate = protocol.get("adoption_gate", {})
    ablation = protocol.get("action_ablation", {})
    forbidden = set(protocol.get("forbidden", []))

    if protocol.get("status") != "LOCKED_BEFORE_OOS_RESULTS":
        raise BusinessGuardProtocolError("protocol must be locked")
    if (
        data.get("availability_time") != "SEC_ACCEPTANCE_DATETIME"
        or data.get("restatement_backfill_forbidden") is not True
        or data.get("allowed_taxonomies") != ["us-gaap"]
        or data.get("duration_days_quarterly_minimum") != 70
        or data.get("duration_days_quarterly_maximum") != 120
        or data.get("maximum_fact_age_days", 9999) > 550
    ):
        raise BusinessGuardProtocolError("invalid point-in-time data contract")
    if set(features) != {
        "REVENUE", "EARNINGS", "OPERATING_CASH_FLOW", "DEBT_BURDEN"
    }:
        raise BusinessGuardProtocolError("business evidence groups changed")
    if (
        guard.get("research_unknown_policy")
        != "EXCLUDE_FROM_PREDICTIVE_COMPARISON"
        or guard.get("live_unknown_policy") != "DO_NOT_AUTHORIZE_ADD_BUY"
    ):
        raise BusinessGuardProtocolError("UNKNOWN handling changed")
    if (
        test.get("forward_horizons_months") != [3, 6, 12]
        or test.get("primary_horizon_months") != 6
        or test.get("event_sampling") != "FIRST_MONTH_OF_GUARD_STATE_TRANSITION"
        or "NON_OVERLAPPING" not in test.get("inference_sample", "")
    ):
        raise BusinessGuardProtocolError("invalid predictive test")
    if (
        gate.get("minimum_events_per_side", 0) < 30
        or gate.get("minimum_test_folds_per_side", 0) < 4
        or gate.get("minimum_directional_folds", 0) < 4
        or gate.get("maximum_holm_p_value", 1) > 0.1
        or gate.get("required_primary_outcomes") != 2
    ):
        raise BusinessGuardProtocolError("adoption gate is too weak")
    if (
        ablation.get("candidate_events") != "FLEE_OR_SCATTER_ADD_BUY_ONLY"
        or ablation.get("add_buy_size") != 0.05
        or ablation.get("execution") != "NEXT_TRADING_DAY_OPEN"
    ):
        raise BusinessGuardProtocolError("action role changed")
    if {
        "BUSINESS_GUARD_CHANGES_HERD_SCORE",
        "BUSINESS_GUARD_CREATES_SELL_SIGNAL",
        "UNKNOWN_TREATED_AS_DETERIORATED_IN_PREDICTIVE_TEST",
        "FUTURE_RESTATEMENT_BACKFILL",
        "THRESHOLD_SEARCH_AFTER_RESULTS",
    } - forbidden:
        raise BusinessGuardProtocolError("unsafe shortcut is not forbidden")
    return {
        "protocol_version": protocol["protocol_version"],
        "status": protocol["status"],
        "feature_count": len(features),
        "sha256": registry_sha256(protocol),
    }


def load_protocol(path: Path = PROTOCOL_PATH) -> tuple[dict, dict]:
    protocol = json.loads(Path(path).read_text(encoding="utf-8"))
    return protocol, validate_protocol(protocol)


if __name__ == "__main__":
    _, audit = load_protocol()
    print(json.dumps(audit, ensure_ascii=False, indent=2))
