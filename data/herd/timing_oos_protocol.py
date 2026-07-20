"""역할을 보존한 HERD OOS 검증 프로토콜을 검증한다."""

from __future__ import annotations

import json
from pathlib import Path

from herd.timing_hypothesis_registry import TimingHypothesisRegistryError

PROTOCOL_PATH = Path(__file__).with_name("timing_oos_protocol.json")
EXPECTED_FAMILIES = {
    "PRICE_EXTENSION",
    "TREND_MATURITY",
    "RELATIVE_OVERHEAT",
    "PARTICIPATION",
    "MARKET_RISK",
    "BUSINESS_GUARD",
}


def validate_protocol(protocol: dict) -> dict:
    execution = protocol.get("common_execution", {})
    if (
        protocol.get("status") != "LOCKED_BEFORE_OOS_RESULTS"
        or execution.get("execution") != "NEXT_TRADING_DAY_OPEN"
        or execution.get("minimum_exposure", 0) < 0.8
        or execution.get("maximum_monthly_change", 1) > 0.15
        or execution.get("initial_exposure") != 1.0
    ):
        raise TimingHypothesisRegistryError("invalid OOS execution contract")
    tests = protocol.get("tests", [])
    families = {item.get("family") for item in tests}
    if families != EXPECTED_FAMILIES or len(tests) != len(families):
        raise TimingHypothesisRegistryError("OOS evidence roles are incomplete")
    by_family = {item["family"]: item for item in tests}
    if (
        by_family["PARTICIPATION"]["action_test"]
        != "PRICE_EXTENSION_AND_TREND_GATED_ABLATION"
        or by_family["MARKET_RISK"]["action_test"]
        != "ACTION_INTENSITY_CAP_ABLATION"
        or by_family["BUSINESS_GUARD"]["action_test"]
        != "ADD_BUY_VETO_ABLATION"
    ):
        raise TimingHypothesisRegistryError("evidence role was changed")
    forbidden = set(protocol["action_candidate"].get("forbidden", []))
    if {"SELL_FROM_HIGH_RSI_ALONE", "FULL_LIQUIDATION"} - forbidden:
        raise TimingHypothesisRegistryError("unsafe action shortcut")
    return {
        "protocol_version": protocol["protocol_version"],
        "test_count": len(tests),
        "status": protocol["status"],
    }


def load_protocol(path: Path = PROTOCOL_PATH) -> tuple[dict, dict]:
    protocol = json.loads(Path(path).read_text(encoding="utf-8"))
    return protocol, validate_protocol(protocol)


if __name__ == "__main__":
    _, result = load_protocol()
    print(json.dumps(result, ensure_ascii=False, indent=2))
