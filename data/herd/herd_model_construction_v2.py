"""채택된 방향 증거와 중복성 감사가 없으면 B0~B5 HERD 후보를 만들지 않는다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = Path(__file__).with_suffix(".json")


def evaluate_construction(policy_path: Path = POLICY_PATH) -> dict:
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    if policy.get("policy_version") != "HERD_MODEL_CONSTRUCTION_V2" \
            or policy.get("status") != "LOCKED_AFTER_REDUNDANCY_GATE":
        raise ValueError("HERD construction policy is not locked")

    reports = {}
    for name, relative in policy["required_reports"].items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ValueError(f"required report missing: {name}")
        reports[name] = json.loads(path.read_text(encoding="utf-8"))

    oos = reports["independent_oos"]
    redundancy = reports["redundancy_gate"]
    admitted = oos.get("passing_direction_variants", [])
    profit_take_ready = oos.get("profit_take_evidence_ready") is True
    redundancy_ready = redundancy.get("status") == policy["minimum_requirements"]["redundancy_audit_status"]
    eligible = (
        profit_take_ready
        and len(admitted) >= policy["minimum_requirements"]["profit_take_direction"]
        and redundancy_ready
    )

    return {
        "report_version": "herd-model-construction-v2",
        "status": "READY_TO_CONSTRUCT_CANDIDATES" if eligible else "NO_CANDIDATE_CONSTRUCTED",
        "admitted_direction_features": admitted,
        "profit_take_direction_ready": profit_take_ready,
        "redundancy_audit_ready": redundancy_ready,
        "candidate_families_planned": [item["id"] for item in policy["candidate_families"]],
        "candidate_families_constructed": [],
        "candidate_count": 0,
        "weights": {},
        "weights_allowed": False,
        "model_promotion_allowed": False,
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = evaluate_construction()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
