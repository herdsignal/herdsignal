"""V1~V8 미검수 accession에서 V9 독립 원문 표본을 잠근다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_block_extraction_v1 import select_stratified_review
from herd.sec_guidance_structure_parser_v9 import audit_v8_review, transform_candidate


PROTOCOL = Path(__file__).with_suffix(".json")
IDENTITY = [
    "source_sha256", "metric", "fiscal_period", "accounting_basis", "metric_subtype",
    "unit", "lower_bound", "upper_bound", "source_structure", "range_offset",
]


def build(protocol: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    source = pd.concat(
        [pd.read_csv(path, dtype={"cik": str}) for path in protocol["candidate_ledgers"]],
        ignore_index=True,
    ).drop_duplicates(IDENTITY).reset_index(drop=True)
    candidates = pd.DataFrame([
        item for _, row in source.iterrows() if (item := transform_candidate(row)) is not None
    ])
    if not candidates.empty:
        candidates = candidates.drop_duplicates(IDENTITY)
        candidates["review_priority"] = candidates.apply(lambda row: hashlib.sha256(
            f'{row["source_sha256"]}:{row["source_structure"]}:{row["range_offset"]}:{row["metric"]}:V9'.encode()
        ).hexdigest(), axis=1)

    excluded: set[str] = set()
    for path in protocol["development_reviews"]:
        excluded.update(pd.read_csv(path)["accession_number"].astype(str))
    holdout = candidates.loc[
        ~candidates["accession_number"].astype(str).isin(excluded)
    ].copy() if not candidates.empty else candidates.copy()
    gate = protocol["review_gate"]
    stratified = select_stratified_review(holdout, gate["target_rows_per_metric"])
    ranked = holdout.sort_values("review_priority")
    coverage_seed = (
        ranked.groupby("ticker", group_keys=False).head(1)
        .sort_values("review_priority").head(gate["minimum_distinct_tickers"])
    )
    selected = set(stratified.index) | set(coverage_seed.index)
    target = min(gate["minimum_stratified_rows"], len(holdout))
    for index in ranked.index:
        if len(selected) >= target:
            break
        selected.add(index)
    if len(selected) > target:
        seeds = set(coverage_seed.index)
        remainder = [index for index in ranked.index if index in selected and index not in seeds]
        selected = seeds | set(remainder[:max(0, target - len(seeds))])
    review = holdout.loc[sorted(selected)].sort_values(["metric", "review_priority"]).copy()
    if not review.empty:
        review.insert(0, "review_id", [f"SG9-{number:04d}" for number in range(1, len(review) + 1)])
        review["review_decision"] = "PENDING"
        review["review_reason"] = ""
        review["reviewer"] = ""
        review["reviewed_at"] = ""
    ready = bool(
        len(review) >= gate["minimum_stratified_rows"]
        and review["ticker"].nunique() >= gate["minimum_distinct_tickers"]
    ) if not review.empty else False
    report = {
        "report_version": "herd-sec-guidance-v9-independent-validation-v1",
        "input_candidates": len(source),
        "v9_candidates": len(candidates),
        "v9_candidate_tickers": int(candidates["ticker"].nunique()) if not candidates.empty else 0,
        "development_accessions_excluded": len(excluded),
        "fresh_holdout_candidates": len(holdout),
        "fresh_holdout_tickers": int(holdout["ticker"].nunique()) if not holdout.empty else 0,
        "review_rows": len(review),
        "review_tickers": int(review["ticker"].nunique()) if not review.empty else 0,
        "coverage_seed_tickers": int(coverage_seed["ticker"].nunique()) if not coverage_seed.empty else 0,
        "review_sample_gate_ready": ready,
        "review_gate_passed": False,
        "ready_for_direction_preregistration": False,
        "next_decision": "COMPLETE_LOCKED_V9_SOURCE_REVIEW" if ready else "V9_INDEPENDENT_SAMPLE_COVERAGE_BLOCKED",
        "price_outcomes_observed": False,
        "operational_action_ratio": 0.0,
    }
    report.update(audit_v8_review(protocol["development_reviews"][-1]))
    return candidates, review, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    candidates, review, report = build(protocol)
    candidates.to_csv(args.candidates, index=False, float_format="%.12g", lineterminator="\n")
    review.to_csv(args.review, index=False, float_format="%.12g", lineterminator="\n")
    report["protocol_sha256"] = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    report["candidate_sha256"] = hashlib.sha256(args.candidates.read_bytes()).hexdigest()
    report["review_sha256"] = hashlib.sha256(args.review.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
