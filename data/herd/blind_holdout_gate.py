"""차세대 HERD Blind holdout 개방 전제조건을 fail-closed로 판정한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def decide(
    candidate_report: dict,
    data_quality_report: dict,
    generalization_report: dict,
    pre_holdout_gate: dict,
) -> dict:
    summaries = candidate_report.get("summary", {})
    passing_candidates = [
        candidate
        for candidate, metrics in summaries.items()
        if metrics.get("median_excess_cagr") is not None
        and metrics["median_excess_cagr"] > 0
        and metrics.get("positive_excess_rate", 0) >= 60
        and metrics.get("median_upside_capture", 0) >= 0.85
        and metrics.get("median_downside_capture", 2) <= 0.90
        and metrics.get("median_mdd_improvement", -1) >= 0
    ]
    quality_summary = data_quality_report.get("summary", {})
    readiness = data_quality_report.get("readiness", {})
    survivorship = data_quality_report.get("survivorship_coverage", {})
    point_in_time_ready = (
        (
            quality_summary.get("overall_status") == "READY"
            and quality_summary.get("point_in_time_universe_ready") is True
        )
        or (
            readiness.get("status") == "READY"
            and readiness.get("point_in_time_fundamental_model_ready") is True
            and survivorship.get("point_in_time_ready") is True
        )
    )
    walk_forward_ready = (
        generalization_report.get("walk_forward", {}).get("status") == "COMPLETE"
        and generalization_report.get("era_validation", {}).get("status") == "COMPLETE"
    )
    prerequisites = {
        "candidate_passed_pre_holdout_gate": bool(passing_candidates),
        "full_pre_holdout_gate_passed": (
            pre_holdout_gate.get("stage") == "PRE_HOLDOUT"
            and pre_holdout_gate.get("status") == "READY_FOR_BLIND_HOLDOUT"
            and pre_holdout_gate.get("eligible_for_holdout") is True
            and not pre_holdout_gate.get("failed_criteria")
        ),
        "point_in_time_data_ready": point_in_time_ready,
        "walk_forward_and_era_validation_complete": walk_forward_ready,
    }
    can_open = all(prerequisites.values())
    return {
        "policy_version": "2026.07-v2",
        "holdout_id": "HERD_VNEXT_UNASSIGNED",
        "status": "READY_TO_OPEN" if can_open else "NOT_OPENED_PREREQUISITES_FAILED",
        "evaluation_count": 0,
        "candidate_id": passing_candidates[0] if len(passing_candidates) == 1 else None,
        "passed": None,
        "sealed_data_accessed": False,
        "prerequisites": prerequisites,
        "failed_prerequisites": [name for name, passed in prerequisites.items() if not passed],
        "legacy_v61_holdout_reusable": False,
        "automatic_promotion": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--data-quality", type=Path, required=True)
    parser.add_argument("--generalization", type=Path, required=True)
    parser.add_argument("--adoption-gate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = decide(
        json.loads(args.candidates.read_text(encoding="utf-8")),
        json.loads(args.data_quality.read_text(encoding="utf-8")),
        json.loads(args.generalization.read_text(encoding="utf-8")),
        json.loads(args.adoption_gate.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
