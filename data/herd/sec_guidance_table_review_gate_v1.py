"""잠긴 SEC 가이던스 표본 검수의 정확도와 승격 게이트를 계산한다."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd


ALLOWED = {"PENDING", "VALID", "INVALID", "AMBIGUOUS"}


def wilson_lower(successes: int, total: int, z: float = 1.959963984540054) -> float | None:
    if total == 0:
        return None
    proportion = successes / total
    denominator = 1 + z * z / total
    center = proportion + z * z / (2 * total)
    margin = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total))
    return (center - margin) / denominator


def evaluate(review: pd.DataFrame, protocol: dict) -> dict:
    decisions = set(review["review_decision"].fillna("PENDING"))
    unknown = sorted(decisions - ALLOWED)
    if unknown:
        raise ValueError(f"Unknown review decisions: {unknown}")
    decided = review.loc[review["review_decision"].isin(["VALID", "INVALID", "AMBIGUOUS"])]
    valid = int(decided["review_decision"].eq("VALID").sum())
    total = len(decided)
    lower = wilson_lower(valid, total)
    gate = protocol["review_gate"]
    complete = len(review) >= gate["minimum_stratified_rows"] and total == len(review)
    passed = complete and lower is not None and lower >= gate["minimum_wilson_95_lower_bound"]
    return {
        "review_rows": len(review),
        "reviewed_rows": total,
        "valid_rows": valid,
        "invalid_rows": int(decided["review_decision"].eq("INVALID").sum()),
        "ambiguous_rows": int(decided["review_decision"].eq("AMBIGUOUS").sum()),
        "source_precision": valid / total if total else None,
        "wilson_95_lower_bound": lower,
        "review_complete": complete,
        "review_gate_passed": passed,
        "ready_to_build_revision_pairs": passed,
        "ready_for_direction_preregistration": False,
        "next_decision": "BUILD_SOURCE_QUALIFIED_REVISION_PAIRS" if passed else "REVIEW_GATE_BLOCKED",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(pd.read_csv(args.review), json.loads(args.protocol.read_text()))
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
