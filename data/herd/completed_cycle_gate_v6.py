"""최신 익절·재진입 증거와 공정 기준선을 연결하는 완결 사이클 게이트."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
REPORT_PATH = ROOT / "data/reports/completed_cycle_gate_v6.json"
VERSION = "HERD_COMPLETED_CYCLE_GATE_V6"


class CompletedCycleGateV6Error(ValueError):
    pass


def _load(item: dict[str, str]) -> dict[str, Any]:
    path = (ROOT / item["path"]).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise CompletedCycleGateV6Error(f"missing input: {item['path']}")
    if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
        raise CompletedCycleGateV6Error(f"input changed: {item['path']}")
    return json.loads(path.read_text())


def build_report(output_path: Path = REPORT_PATH) -> dict[str, Any]:
    contract = json.loads(CONTRACT_PATH.read_text())
    if (
        contract.get("gate_version") != VERSION
        or contract.get("status") != "LOCKED_BEFORE_GATE_RESULT"
    ):
        raise CompletedCycleGateV6Error("completed-cycle gate is not locked")
    evidence, reentry, simple, cashflow, protocol = [
        _load(item) for item in contract["inputs"]
    ]
    checks = {
        "profit_take_direction":
            len(evidence["admitted_families"]) > 0,
        "conditional_reentry":
            reentry["status"] == "REENTRY_READY_FOR_CYCLE",
        "simple_baselines":
            simple["status"] == "SIMPLE_BASELINE_FLOORS_ESTABLISHED",
        "cashflow_contract":
            cashflow["status"] == "CASHFLOW_BENCHMARK_CONTRACT_VERIFIED",
        "minimum_oos_folds":
            protocol["evaluation"]["minimum_complete_oos_folds"] >= 4,
        "minimum_oos_years":
            protocol["evaluation"]["minimum_oos_years"] >= 5,
    }
    eligible = all(checks.values())
    firewall = contract["execution_firewall"]
    if firewall["simulation_allowed"] is not False:
        raise CompletedCycleGateV6Error("simulation firewall was widened")
    report = {
        "report_version": VERSION,
        "status": (
            "READY_FOR_COMPLETED_CYCLE"
            if eligible
            else "BLOCKED_INCOMPLETE_DIRECTION_EVIDENCE"
        ),
        "checks": checks,
        "blocked_reasons": [
            name for name, passed in checks.items() if not passed
        ],
        "completed_cycle_executed": False,
        "buy_hold_comparison_executed": False,
        "cost_stress_executed": False,
        "blind_holdout_access": False,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(build_report(), indent=2))
