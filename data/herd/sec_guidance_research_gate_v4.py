"""V4 독립 원문 정확도 결과로 SEC 가이던스 연구 3~8을 fail-closed한다."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import pandas as pd


V5_REQUIREMENTS = [
    "PARSE_COMPACT_QUARTER_AND_FISCAL_YEAR_AS_ONE_PERIOD",
    "SELECT_CURRENT_RANGE_WHEN_PRIOR_RANGE_FOLLOWS_FROM",
    "BIND_EX_PENSION_MTM_AS_NON_GAAP_BASIS",
    "PRESERVE_AFTER_DIVIDENDS_FREE_CASH_FLOW_SUBTYPE",
    "REJECT_OR_EXPLODE_ONE_RANGE_WITH_MULTIPLE_ACCOUNTING_BASES",
    "DISTINGUISH_REPORTING_QUARTER_FROM_ANNUAL_GUIDANCE",
]


def build_gate_state(protocol: dict, review: dict, labels: pd.DataFrame) -> dict:
    passed = bool(review["review_gate_passed"])
    steps = []
    for index, name in enumerate(protocol["steps"], start=1):
        if index == 1:
            status = "COMPLETE"
            reason = f"{review['reviewed_rows']} unseen rows across {review['distinct_tickers']} issuers adjudicated"
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
    failures = labels.loc[labels["review_decision"].ne("VALID"), "review_reason"]
    return {
        "report_version": "herd-sec-guidance-research-gate-v4",
        "decision": "PARSER_V5_REQUIRED" if not passed else "BUILD_SOURCE_QUALIFIED_REVISION_PAIRS",
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
        "next_parser_requirements": V5_REQUIREMENTS,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    protocol = json.loads(Path(__file__).with_suffix(".json").read_text(encoding="utf-8"))
    review = json.loads((root / protocol["source_review_report"]).read_text(encoding="utf-8"))
    labels = pd.read_csv(root / protocol["source_review_labels"])
    report = build_gate_state(protocol, review, labels)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
