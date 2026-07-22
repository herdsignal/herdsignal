"""SEC 가이던스 연구 1~8단계를 앞 단계의 증거로만 개방한다."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import pandas as pd


def build_gate_state(protocol: dict, review: dict, labels: pd.DataFrame) -> dict:
    passed = bool(review.get("review_gate_passed"))
    steps = []
    for index, name in enumerate(protocol["steps"], start=1):
        if index == 1:
            status = "COMPLETE"
            reason = f"{review['reviewed_rows']} independent rows adjudicated"
        elif index == 2:
            status = "PASSED" if passed else "FAILED"
            reason = (
                f"Wilson lower {review['wilson_95_lower_bound']:.4f} "
                f"vs required {protocol['required_wilson_95_lower_bound']:.4f}"
            )
        else:
            status = "READY" if passed and index == 3 else "BLOCKED"
            reason = "SOURCE_PRECISION_GATE_FAILED" if not passed else "PREVIOUS_STEP_NOT_COMPLETE"
        steps.append({"step": index, "name": name, "status": status, "reason": reason})

    failures = labels.loc[labels["review_decision"] != "VALID", "review_reason"]
    return {
        "report_version": "herd-sec-guidance-research-gate-v2",
        "decision": "PARSER_V3_REQUIRED" if not passed else "BUILD_SOURCE_QUALIFIED_REVISION_PAIRS",
        "steps": steps,
        "failure_taxonomy": dict(Counter(failures)),
        "source_precision": review["source_precision"],
        "wilson_95_lower_bound": review["wilson_95_lower_bound"],
        "source_qualified_revision_pairs": 0,
        "direction_hypotheses_preregistered": 0,
        "price_outcomes_observed": False,
        "evidence_admitted": False,
        "completed_cycle_executed": False,
        "operational_action_ratio": protocol["operational_action_ratio_before_admission"],
        "next_parser_requirements": [
            "DISTINGUISH_COMPARISON_PERIOD_FROM_GUIDANCE_PERIOD",
            "BIND_METRIC_AND_ACCOUNTING_BASIS_TO_EACH_RANGE",
            "SEPARATE_ACTUAL_PRIOR_CURRENT_AND_SINGLE_VALUES",
            "PRESERVE_SEGMENT_AND_METRIC_SUBTYPES",
            "REJECT_REVERSED_OR_IMPLAUSIBLE_SCALES"
        ]
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    protocol = json.loads(Path(__file__).with_suffix(".json").read_text(encoding="utf-8"))
    review = json.loads((root / protocol["source_review_report"]).read_text(encoding="utf-8"))
    labels = pd.read_csv(root / "data/herd/sec_guidance_structure_review_labels_v2.csv")
    report = build_gate_state(protocol, review, labels)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
