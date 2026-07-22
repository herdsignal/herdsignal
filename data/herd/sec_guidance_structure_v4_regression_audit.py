"""V3 원문 오류가 V4에서 동일 객체로 재생성되는지 감사한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


IDENTITY = ["ticker", "accession_number", "metric", "fiscal_period", "accounting_basis", "unit"]


def audit(v3_review: pd.DataFrame, v4_candidates: pd.DataFrame) -> dict:
    retained = []
    for row in v3_review.itertuples(index=False):
        matches = v4_candidates
        for field in IDENTITY:
            matches = matches.loc[matches[field].astype(str).eq(str(getattr(row, field)))]
        low_tolerance = 1e-8 * max(1.0, abs(float(row.lower_bound)))
        high_tolerance = 1e-8 * max(1.0, abs(float(row.upper_bound)))
        matches = matches.loc[
            matches["lower_bound"].sub(float(row.lower_bound)).abs().le(low_tolerance)
            & matches["upper_bound"].sub(float(row.upper_bound)).abs().le(high_tolerance)
        ]
        if not matches.empty:
            retained.append({
                "review_id": row.review_id,
                "review_decision": row.review_decision,
                "review_reason": row.review_reason,
            })
    retained_frame = pd.DataFrame(retained)
    invalid = retained_frame.loc[retained_frame["review_decision"].eq("INVALID")] if not retained_frame.empty else retained_frame
    valid = retained_frame.loc[retained_frame["review_decision"].eq("VALID")] if not retained_frame.empty else retained_frame
    return {
        "report_version": "herd-sec-guidance-structure-v4-regression-audit",
        "v3_review_rows": len(v3_review),
        "v3_valid_rows": int(v3_review["review_decision"].eq("VALID").sum()),
        "v3_invalid_rows": int(v3_review["review_decision"].eq("INVALID").sum()),
        "v4_exact_valid_bindings_retained": len(valid),
        "v4_exact_invalid_bindings_retained": len(invalid),
        "invalid_review_ids_retained": invalid["review_id"].tolist() if not invalid.empty else [],
        "development_regression_passed": invalid.empty,
        "independent_precision_inferred": False,
        "price_outcomes_observed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v3-review", type=Path, required=True)
    parser.add_argument("--v4-candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(pd.read_csv(args.v3_review), pd.read_csv(args.v4_candidates))
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
