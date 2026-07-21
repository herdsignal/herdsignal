"""독립 OOS 통과 증거가 없으면 중복성·조건부 효과 학습을 차단한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = Path(__file__).with_suffix(".json")


def evaluate_redundancy_gate(policy_path: Path = POLICY_PATH) -> dict:
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    if policy.get("policy_version") != "HERD_EVIDENCE_REDUNDANCY_GATE_V2" \
            or policy.get("status") != "LOCKED_AFTER_INDEPENDENT_OOS":
        raise ValueError("evidence redundancy policy is not locked")

    source = (ROOT / policy["source_report"]).resolve()
    if not source.is_relative_to(ROOT) or not source.is_file():
        raise ValueError("candidate OOS report is missing or outside repository")
    oos = json.loads(source.read_text(encoding="utf-8"))
    admitted = oos.get(policy["admission_field"], [])
    if oos.get("weights_allowed") is not False or oos.get("blind_holdout_access") is not False:
        raise ValueError("candidate OOS safety contract changed")

    eligible = len(admitted) >= policy["minimum_admitted_features"]
    return {
        "report_version": "herd-evidence-redundancy-gate-v2",
        "status": "READY_FOR_REDUNDANCY_AUDIT" if eligible else "BLOCKED_NO_INDEPENDENT_OOS_EVIDENCE",
        "admitted_direction_features": admitted,
        "admitted_count": len(admitted),
        "minimum_required": policy["minimum_admitted_features"],
        "correlation_audit_executed": False,
        "conditional_effect_audit_executed": False,
        "ablation_executed": False,
        "weights_allowed": False,
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
        "blocked_audit_is_performance_failure": False,
        "planned_methods_if_eligible": policy["planned_methods_if_eligible"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = evaluate_redundancy_gate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
