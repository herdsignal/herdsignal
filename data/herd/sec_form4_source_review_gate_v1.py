"""잠긴 Form 4 원문 판정의 coverage·정확도 게이트를 평가한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_table_review_gate_v1 import wilson_lower
from herd.sec_form4_accession_catalog_v1 import load_protocol


def evaluate(review_path: Path, atomic_path: Path, protocol_path: Path) -> dict:
    protocol = load_protocol(protocol_path)
    gate = protocol["source_review_gate"]
    review = pd.read_csv(review_path, keep_default_na=False)
    atomic = pd.read_csv(atomic_path, keep_default_na=False)
    allowed = set(gate["labels"])
    decisions = review["reviewDecision"].astype(str)
    unexpected = sorted(set(decisions) - allowed - {"PENDING"})
    if unexpected:
        raise ValueError(f"unexpected source review labels: {unexpected}")
    population_codes = set(atomic["transactionCode"].astype(str))
    reviewed_codes = set(review["transactionCode"].astype(str))
    code_volume_coverage = float(
        atomic["transactionCode"].isin(reviewed_codes).mean()
    )
    completed = decisions.isin(allowed)
    total = len(review)
    valid = int(decisions.eq("VALID").sum())
    invalid = int(decisions.eq("INVALID").sum())
    ambiguous = int(decisions.eq("AMBIGUOUS").sum())
    pending = int(decisions.eq("PENDING").sum())
    completed_count = int(completed.sum())
    accuracy = valid / completed_count if completed_count else None
    lower = wilson_lower(valid, total) if pending == 0 else None
    passed = all([
        pending == 0,
        total >= gate["minimum_reviewed_transactions"],
        review["issuerCik"].nunique() >= gate["minimum_distinct_issuers"],
        code_volume_coverage >= gate["minimum_transaction_code_coverage"],
        reviewed_codes == population_codes,
        accuracy is not None
        and accuracy >= gate["minimum_required_field_accuracy"],
        lower is not None and lower >= gate["minimum_wilson_95_lower_bound"],
    ])
    return {
        "report_version": "HERD_SEC_FORM4_SOURCE_REVIEW_GATE_V1",
        "status": "SOURCE_REVIEW_PASSED" if passed else (
            "SOURCE_REVIEW_PENDING" if pending else "SOURCE_REVIEW_FAILED"
        ),
        "sample_transactions": total,
        "sample_issuers": int(review["issuerCik"].nunique()),
        "population_transaction_codes": sorted(population_codes),
        "reviewed_transaction_codes": sorted(reviewed_codes),
        "transaction_code_volume_coverage": code_volume_coverage,
        "valid": valid,
        "invalid": invalid,
        "ambiguous": ambiguous,
        "pending": pending,
        "required_field_accuracy": accuracy,
        "wilson_95_lower_bound": lower,
        "accuracy_gate_passed": passed,
        "price_outcomes_opened": False,
        "direction_hypothesis_allowed": passed,
        "operational_action_authority": False,
        "next_decision": (
            "PREREGISTER_ONE_FORM4_HYPOTHESIS"
            if passed else "COMPLETE_OR_REPAIR_PRIMARY_SOURCE_REVIEW"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review", type=Path)
    parser.add_argument("atomic", type=Path)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.review, args.atomic, args.protocol)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
