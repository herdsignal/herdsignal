"""익절 현금·기업 상태·회복 확인 순서를 강제하는 재진입 게이트."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
REPORT_PATH = ROOT / "data/reports/conditional_reentry_gate_v2.json"
VERSION = "HERD_CONDITIONAL_REENTRY_GATE_V2"


class ConditionalReentryGateError(ValueError):
    pass


def _load(item: dict[str, str]) -> dict[str, Any]:
    path = (ROOT / item["path"]).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ConditionalReentryGateError(f"missing input: {item['path']}")
    if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
        raise ConditionalReentryGateError(f"input changed: {item['path']}")
    return json.loads(path.read_text())


def build_report(output_path: Path = REPORT_PATH) -> dict[str, Any]:
    contract = json.loads(CONTRACT_PATH.read_text())
    if (
        contract.get("gate_version") != VERSION
        or contract.get("status") != "LOCKED_BEFORE_GATE_RESULT"
    ):
        raise ConditionalReentryGateError("reentry gate is not locked")
    evidence, confirmed, business, discovery, insider = [
        _load(item) for item in contract["inputs"]
    ]
    validated_cash = bool(evidence["admitted_families"])
    checks = {
        "validated_profit_take_cash": validated_cash,
        "confirmed_reentry_rule": confirmed["reentry_authorized"] is True,
        "pit_business_veto": business["primary_outcomes_passed"]
        >= business["primary_outcomes_required"],
        "new_recovery_feature": len(discovery["retained_features"]) > 0,
        "independent_insider_support": insider["result"]["passed"] is True,
    }
    firewall = contract["firewall"]
    if (
        firewall["reentry_simulation_allowed"] is not False
        or firewall["blind_holdout_access"] is not False
        or firewall["operational_action_ratio"] != 0.0
    ):
        raise ConditionalReentryGateError("reentry firewall was widened")
    report = {
        "report_version": VERSION,
        "status": "REENTRY_BLOCKED_NO_VALIDATED_PROFIT_TAKE_CASH",
        "checks": checks,
        "eligible_cash_events": 0,
        "reentry_simulation_executed": False,
        "next_gate": "PROFIT_TAKE_DIRECTION_EVIDENCE",
        "blind_holdout_access": False,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(build_report(), indent=2))
