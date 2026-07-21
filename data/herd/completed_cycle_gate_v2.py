"""독립 OOS 증거가 모두 통과했을 때만 5% 완결 사이클 연구를 연다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from herd.evidence_admission_v2 import load_evidence_admission_v2


ROOT = Path(__file__).resolve().parents[2]


def evaluate_completed_cycle_gate() -> dict:
    _, admission = load_evidence_admission_v2()
    business = json.loads(
        (ROOT / "data/reports/business_state_oos_v2.json").read_text(encoding="utf-8")
    )
    profit_ready = admission["admitted_profit_take_count"] > 0
    business_ready = business.get("add_buy_veto_authorized") is True
    allowed = profit_ready and business_ready
    return {
        "gate_version": "HERD_COMPLETED_CYCLE_GATE_V2",
        "status": "READY_FOR_5_PERCENT_RESEARCH" if allowed else "BLOCKED_MISSING_INDEPENDENT_EVIDENCE",
        "profit_take_evidence_ready": profit_ready,
        "business_state_evidence_ready": business_ready,
        "completed_cycle_evaluation_executed": False,
        "completed_cycle_allowed": allowed,
        "initial_profit_take_fraction": 0.05 if allowed else 0.0,
        "reentry_maximum": "OPEN_SALE_CASH" if allowed else "BLOCKED",
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
        "forbidden": [
            "RUN_CYCLE_WITHOUT_PROFIT_TAKE_EVIDENCE",
            "RUN_CYCLE_WITHOUT_BUSINESS_OR_REENTRY_EVIDENCE",
            "INCREASE_INITIAL_FRACTION_ABOVE_5_PERCENT",
            "TREAT_BLOCKED_CYCLE_AS_FAILED_PERFORMANCE_TEST"
        ]
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = evaluate_completed_cycle_gate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
