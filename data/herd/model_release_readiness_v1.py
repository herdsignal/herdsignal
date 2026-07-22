"""차세대 HERD의 일반화·비용·PIT·Blind holdout 선행 조건을 최종 판정한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PROTOCOL = Path(__file__).with_suffix(".json")


def evaluate(protocol: dict) -> dict:
    paths = {name: Path(path) for name, path in protocol["required_reports"].items()}
    reports = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in paths.items()}
    model, cycle = reports["model"], reports["cycle"]
    survivorship, legacy, blind = reports["survivorship"], reports["legacy_generalization"], reports["blind_holdout"]
    candidate_exists = model.get("candidate_count", 0) > 0
    checks = {
        "candidate_exists": candidate_exists,
        "direction_evidence_admitted": bool(model.get("admitted_direction_evidence")),
        "completed_cycle_passed": bool(cycle.get("completed_cycle_executed")) and bool(cycle.get("model_promotion_allowed")),
        "base_and_stress_costs_passed": bool(cycle.get("cost_stress_executed")) and bool(cycle.get("model_promotion_allowed")),
        "walk_forward_and_era_validation_passed": candidate_exists and legacy.get("walk_forward", {}).get("status") == "PASS" and legacy.get("era_validation", {}).get("status") == "PASS",
        "survivorship_safe": bool(survivorship.get("survivorship_safe")),
        "blind_holdout_still_sealed": blind.get("evaluation_count") == 0 and blind.get("sealed_data_accessed") is False,
    }
    ready = all(checks.values())
    return {
        "report_version": "HERD_MODEL_RELEASE_READINESS_V1",
        "status": "READY_TO_ASSIGN_SINGLE_BLIND_HOLDOUT" if ready else "RESEARCH_BLOCKED_NO_RELEASABLE_MODEL",
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "legacy_generalization_reused_for_new_candidate": False,
        "blind_holdout_evaluation_count": int(blind["evaluation_count"]),
        "blind_holdout_access": False,
        "production_signal_allowed": False,
        "operational_action_ratio": 0.0,
        "input_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()},
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
