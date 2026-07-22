"""승인된 익절·재진입·기업 상태가 모두 있을 때만 동일 5% 완결 사이클을 연다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PROTOCOL = Path(__file__).with_suffix(".json")


def evaluate(protocol: dict) -> dict:
    reports = {name: json.loads(Path(path).read_text(encoding="utf-8")) for name, path in protocol["required_reports"].items()}
    checks = {
        "constructed_candidate": reports["model"].get("candidate_count", 0) > 0,
        "profit_take_direction": bool(reports["profit_take"]["decision"].get("profit_take_evidence_admitted", False)),
        "reentry_direction": bool(reports["reentry"].get("reentry_authorized", False)),
        "sec_pit_business_veto": bool(reports["business_veto"].get("business_veto_evidence_admitted", False)),
    }
    eligible = all(checks.values())
    contract = protocol["execution_contract_if_eligible"]
    return {
        "report_version": "HERD_COMPLETED_CYCLE_GATE_V5",
        "status": "READY_FOR_5_PERCENT_COMPLETED_CYCLE" if eligible else "BLOCKED_INCOMPLETE_EVIDENCE",
        "checks": checks,
        "blocked_reasons": [name for name, passed in checks.items() if not passed],
        "profit_take_fraction": contract["profit_take_fraction"] if eligible else 0.0,
        "reentry_fraction": "MATCHED_PRIOR_SALE_ONLY" if eligible else 0.0,
        "execution_contract_if_eligible": contract,
        "completed_cycle_executed": False,
        "buy_hold_comparison_executed": False,
        "cost_stress_executed": False,
        "model_promotion_allowed": False,
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
        "input_sha256": {
            name: hashlib.sha256(Path(path).read_bytes()).hexdigest()
            for name, path in protocol["required_reports"].items()
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    report = evaluate(protocol)
    report["protocol_sha256"] = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
