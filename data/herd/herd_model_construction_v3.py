"""독립 OOS 통과 증거만 차세대 HERD 후보 구성으로 전달한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = Path(__file__).with_suffix(".json")


def _repository_report(relative: str) -> object:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ValueError(f"required report missing or outside repository: {relative}")
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_construction(policy_path: Path = POLICY_PATH) -> dict:
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    if policy.get("status") != "LOCKED_AFTER_INDEPENDENT_RUSH_EVIDENCE_V1":
        raise ValueError("model construction V3 policy must be locked")
    if "COMBINE_FAILED_FEATURES" not in policy.get("forbidden", []):
        raise ValueError("failed feature combination must be forbidden")
    oos = _repository_report(policy["required_reports"]["independent_oos"])
    comparison = _repository_report(policy["required_reports"]["comparison"])
    admitted_rows = [row for row in comparison if row.get("admitted") is True]
    admitted = [row["feature"] for row in admitted_rows]
    if admitted != oos.get("admitted_features", []):
        raise ValueError("admitted feature ledger and OOS report disagree")
    eligible = len(admitted) >= policy["minimum_admitted_direction_features"]
    return {
        "report_version": "HERD_MODEL_CONSTRUCTION_V3",
        "status": "READY_FOR_CANDIDATE_ABLATION" if eligible else "BLOCKED_NO_ADMITTED_DIRECTION_EVIDENCE",
        "source_oos_status": oos.get("status"),
        "admitted_direction_features": admitted,
        "rejected_direction_features": [row["feature"] for row in comparison if not row.get("admitted")],
        "candidate_contract": policy["candidate_contract_if_eligible"] if eligible else None,
        "candidate_count": 1 if eligible else 0,
        "weights": {},
        "weights_allowed": False,
        "existing_v4_preserved": True,
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
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
