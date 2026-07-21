"""익절·재진입·PIT 증거가 모두 있을 때만 5% 완결 사이클을 연다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = Path(__file__).with_suffix(".json")


def evaluate_completed_cycle_gate(
    *,
    reentry_direction_features: list[str] | None = None,
    sec_pit_ready: bool = False,
    policy_path: Path = POLICY_PATH,
) -> dict:
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    if policy.get("status") != "LOCKED_AFTER_MODEL_CONSTRUCTION_V3":
        raise ValueError("completed cycle V4 policy must be locked")
    model_path = (ROOT / policy["required_model_report"]).resolve()
    if not model_path.is_relative_to(ROOT) or not model_path.is_file():
        raise ValueError("required model report is missing or outside repository")
    model = json.loads(model_path.read_text(encoding="utf-8"))
    reentry = reentry_direction_features or []
    checks = {
        "constructed_candidate": model.get("candidate_count", 0) > 0,
        "profit_take_direction": bool(model.get("admitted_direction_features")),
        "reentry_direction": bool(reentry),
        "sec_pit_business_state": bool(sec_pit_ready),
    }
    eligible = all(checks.values())
    contract = policy["execution_contract_if_eligible"]
    return {
        "report_version": "HERD_COMPLETED_CYCLE_GATE_V4",
        "status": "READY_FOR_5_PERCENT_CYCLE_RESEARCH" if eligible else "BLOCKED_INCOMPLETE_DIRECTION_OR_PIT_EVIDENCE",
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
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = evaluate_completed_cycle_gate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
