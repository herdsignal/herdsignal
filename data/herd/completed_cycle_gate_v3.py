"""익절·재진입 방향 증거가 모두 없으면 5% 완결 사이클을 실행하지 않는다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = Path(__file__).with_suffix(".json")


def evaluate_completed_cycle_gate(policy_path: Path = POLICY_PATH) -> dict:
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    if policy.get("policy_version") != "HERD_COMPLETED_CYCLE_GATE_V3" \
            or policy.get("status") != "LOCKED_AFTER_MODEL_CONSTRUCTION_V2":
        raise ValueError("completed-cycle V3 policy is not locked")

    source = (ROOT / policy["required_report"]).resolve()
    if not source.is_relative_to(ROOT) or not source.is_file():
        raise ValueError("model construction report is missing or outside repository")
    construction = json.loads(source.read_text(encoding="utf-8"))
    candidate_ready = construction.get("candidate_count", 0) > 0
    profit_take_ready = construction.get("profit_take_direction_ready") is True
    # Reentry requires its own independent target and is never inferred from a sell signal.
    reentry_ready = construction.get("reentry_direction_ready") is True
    eligible = candidate_ready and profit_take_ready and reentry_ready
    contract = policy["execution_contract_if_eligible"]

    return {
        "report_version": "herd-completed-cycle-gate-v3",
        "status": "READY_FOR_5_PERCENT_CYCLE" if eligible else "BLOCKED_MISSING_PROFIT_TAKE_OR_REENTRY_EVIDENCE",
        "constructed_candidate_ready": candidate_ready,
        "profit_take_evidence_ready": profit_take_ready,
        "reentry_evidence_ready": reentry_ready,
        "initial_profit_take_fraction": contract["initial_profit_take_fraction"] if eligible else 0.0,
        "completed_cycle_executed": False,
        "buy_hold_comparison_executed": False,
        "cost_stress_executed": False,
        "execution_contract_if_eligible": contract,
        "blocked_experiment_is_performance_failure": False,
        "model_promotion_allowed": False,
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
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
