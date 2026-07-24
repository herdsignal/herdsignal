"""13F 방향 OOS가 통과하지 않으면 5% 완결 사이클 실행을 차단한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from herd.sec_13f_security_ledger_v1 import ROOT, sha256


CONTRACT = ROOT / "data/herd/sec_13f_completed_cycle_gate_v1.json"
REPORT = ROOT / "data/reports/sec_13f_completed_cycle_gate_v1.json"
FORMAT_VERSION = "SEC_13F_COMPLETED_CYCLE_GATE_V1"


class Sec13fCompletedCycleGateError(RuntimeError):
    """13F 완결 사이클 승격 경계가 변경되면 발생한다."""


def evaluate_gate(
    contract: dict[str, Any],
    upstream: dict[str, Any],
) -> dict[str, Any]:
    passed = (
        upstream.get("status") == contract["required_upstream_status"]
        and upstream.get("decision") == contract["required_upstream_decision"]
        and all(upstream.get("gate_results", {}).values())
    )
    if passed:
        status = "SEC_13F_COMPLETED_CYCLE_RESEARCH_ALLOWED_NOT_EXECUTED"
        next_step = "BUILD_SEPARATE_COMPLETED_CYCLE_PROTOCOL"
        blockers: list[str] = []
    else:
        status = "SEC_13F_COMPLETED_CYCLE_BLOCKED_UPSTREAM"
        next_step = contract["on_failure"]["next_step"]
        blockers = [
            "DIRECTION_HYPOTHESIS_REJECTED",
            *[
                key
                for key, value in upstream.get("gate_results", {}).items()
                if not value
            ],
        ]
    return {
        "report_version": FORMAT_VERSION,
        "status": status,
        "upstream_status": upstream.get("status"),
        "upstream_decision": upstream.get("decision"),
        "upstream_gate_results": upstream.get("gate_results", {}),
        "blockers": blockers,
        "cycle_executed": False,
        "cost_stress_executed": False,
        "completed_cycles": None,
        "economic_metrics": None,
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
        "interpretation": (
            "UPSTREAM_DIRECTION_EVIDENCE_REJECTED_NOT_ZERO_ECONOMIC_RETURN"
            if not passed
            else "ECONOMIC_RESEARCH_REQUIRES_A_NEW_LOCKED_PROTOCOL"
        ),
        "next_step": next_step,
    }


def generate(
    contract_path: Path = CONTRACT,
    report_path: Path = REPORT,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if (
        contract.get("protocol_version") != FORMAT_VERSION
        or contract.get("status") != "LOCKED_UPSTREAM_PROMOTION_GATE"
    ):
        raise Sec13fCompletedCycleGateError("completed-cycle gate is not locked")
    payloads = {}
    for item in contract["pinned_inputs"]:
        path = ROOT / item["path"]
        if not path.is_file() or sha256(path) != item["sha256"]:
            raise Sec13fCompletedCycleGateError(
                f"completed-cycle input changed: {item['path']}"
            )
        payload = json.loads(path.read_text(encoding="utf-8"))
        required = item.get("required_protocol_status")
        if required and payload.get("status") != required:
            raise Sec13fCompletedCycleGateError(
                f"completed-cycle protocol status changed: {item['path']}"
            )
        payloads[item["path"]] = payload
    upstream = payloads[
        "data/reports/sec_13f_crowding_incremental_oos_v1.json"
    ]
    report = evaluate_gate(contract, upstream)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def verify_outputs(report_path: Path = REPORT) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("report_version") != FORMAT_VERSION:
        raise Sec13fCompletedCycleGateError("unexpected completed-cycle report")
    if (
        report["cycle_executed"]
        or report["cost_stress_executed"]
        or report["operational_action_ratio"] != 0.0
        or report["blind_holdout_access"]
    ):
        raise Sec13fCompletedCycleGateError("blocked economics were executed")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    report = verify_outputs() if args.verify_only else generate()
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
