"""13F 1~9단계의 재현성·승격 경계를 하나의 최종 영수증으로 검증한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from herd.sec_13f_security_ledger_v1 import ROOT, sha256


CONTRACT = ROOT / "data/herd/sec_13f_phase_review_v1.json"
REPORT = ROOT / "data/reports/sec_13f_phase_review_v1.json"
FORMAT_VERSION = "SEC_13F_PHASE_REVIEW_V1"
DIRECTION_PATH = "data/reports/sec_13f_crowding_incremental_oos_v1.json"
CYCLE_PATH = "data/reports/sec_13f_completed_cycle_gate_v1.json"


class Sec13fPhaseReviewError(RuntimeError):
    """고정된 13F 연구 체인이나 안전 경계가 바뀌면 발생한다."""


def review_payload(
    contract: dict[str, Any],
    reports: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    firewall = contract["required_firewall"]
    stage_checks = {
        item["path"]: (
            reports[item["path"]].get("status") == item["required_status"]
        )
        for item in contract["pinned_inputs"]
    }
    research_firewall_checks = {
        "all_action_ratios_zero": all(
            report.get("operational_action_ratio") == firewall[
                "operational_action_ratio"
            ]
            for report in reports.values()
        ),
        "all_blind_holdouts_closed": all(
            report.get("blind_holdout_access") is firewall[
                "blind_holdout_access"
            ]
            for report in reports.values()
        ),
        "direction_kept_as_context_only": (
            reports[DIRECTION_PATH].get("decision")
            == firewall["direction_decision"]
        ),
        "completed_cycle_not_executed": (
            reports[CYCLE_PATH].get("cycle_executed")
            is firewall["cycle_executed"]
        ),
        "unexecuted_economics_not_reported_as_zero": (
            reports[CYCLE_PATH].get("economic_metrics")
            is firewall["economic_metrics"]
        ),
    }
    direction = reports[DIRECTION_PATH]
    failed_direction_gates = sorted(
        key
        for key, passed in direction.get("gate_results", {}).items()
        if not passed
    )
    passed = (
        all(stage_checks.values())
        and all(research_firewall_checks.values())
        and bool(failed_direction_gates)
    )
    return {
        "report_version": FORMAT_VERSION,
        "status": (
            "SEC_13F_PHASE_REVIEW_PASSED_WITH_DIRECTION_REJECTED"
            if passed
            else "SEC_13F_PHASE_REVIEW_FAILED"
        ),
        "stage_checks": stage_checks,
        "research_firewall_checks": research_firewall_checks,
        "direction_evidence": {
            "status": direction.get("status"),
            "decision": direction.get("decision"),
            "failed_gates": failed_direction_gates,
            "incremental_roc_auc": direction.get(
                "aggregate_metrics", {}
            ).get("incremental_roc_auc"),
            "candidate_minus_baseline_log_loss": direction.get(
                "aggregate_metrics", {}
            ).get("candidate_minus_baseline_log_loss"),
        },
        "final_scope": {
            "thirteen_f_role": "NON_DIRECTIONAL_SLOW_CROWDING_CONTEXT_ONLY",
            "completed_cycle_allowed": False,
            "herd_weight_change_allowed": False,
            "operational_action_ratio": 0.0,
            "blind_holdout_access": False,
        },
        "next_step": (
            "PRESERVE_13F_PIPELINE_AND_TEST_A_DIFFERENT_ECONOMIC_INFORMATION_FAMILY"
            if passed
            else "STOP_AND_REPAIR_RESEARCH_CHAIN"
        ),
    }


def generate(
    contract_path: Path = CONTRACT,
    report_path: Path = REPORT,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if (
        contract.get("protocol_version") != FORMAT_VERSION
        or contract.get("status")
        != "LOCKED_REPRODUCIBILITY_AND_PROMOTION_REVIEW"
    ):
        raise Sec13fPhaseReviewError("13F phase review contract is not locked")
    reports: dict[str, dict[str, Any]] = {}
    for item in contract["pinned_inputs"]:
        path = ROOT / item["path"]
        if not path.is_file() or sha256(path) != item["sha256"]:
            raise Sec13fPhaseReviewError(
                f"13F phase input changed: {item['path']}"
            )
        reports[item["path"]] = json.loads(
            path.read_text(encoding="utf-8")
        )
    report = review_payload(contract, reports)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def verify_outputs(report_path: Path = REPORT) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if (
        report.get("report_version") != FORMAT_VERSION
        or report.get("status")
        != "SEC_13F_PHASE_REVIEW_PASSED_WITH_DIRECTION_REJECTED"
        or not all(report.get("stage_checks", {}).values())
        or not all(report.get("research_firewall_checks", {}).values())
    ):
        raise Sec13fPhaseReviewError("13F final review no longer passes")
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
