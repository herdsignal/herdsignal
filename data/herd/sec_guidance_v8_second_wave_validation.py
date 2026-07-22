"""V7와 겹치지 않는 2차 코퍼스를 V4→V8로 재생해 검수 표본을 잠근다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_block_extraction_v1 import load_aliases, select_stratified_review
from herd.sec_guidance_structure_parser_v4 import build as build_v4
from herd.sec_guidance_structure_parser_v5 import transform_candidate as transform_v5
from herd.sec_guidance_structure_parser_v6 import SourceLocator, transform_candidate as transform_v6
from herd.sec_guidance_structure_parser_v7 import transform_candidate as transform_v7
from herd.sec_guidance_structure_parser_v8 import transform_candidate as transform_v8


PROTOCOL = Path(__file__).with_suffix(".json")


def _transform(frame: pd.DataFrame, transform, *args) -> pd.DataFrame:
    rows = [item for _, row in frame.iterrows() if (item := transform(row, *args)) is not None]
    return pd.DataFrame(rows)


def _review_accessions(paths: list[str]) -> set[str]:
    accessions: set[str] = set()
    for path in paths:
        accessions.update(pd.read_csv(path)["accession_number"].astype(str))
    return accessions


def build(protocol: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    corpus = Path(protocol["corpus"])
    v4_protocol = {
        "development_reviews": protocol["development_reviews"],
        "review_gate": protocol["review_gate"],
    }
    v4, _, v4_report = build_v4(
        [corpus], load_aliases(Path(protocol["alias_registry"])), v4_protocol,
    )
    v5 = _transform(v4, transform_v5)
    base_v6 = json.loads(Path("data/herd/sec_guidance_structure_parser_v6.json").read_text())
    locator = SourceLocator([*base_v6["source_corpora"], str(corpus)])
    v6 = _transform(v5, transform_v6, locator)
    v7 = _transform(v6, transform_v7)
    candidates = _transform(v7, transform_v8)
    if not candidates.empty:
        candidates["review_priority"] = candidates.apply(lambda row: hashlib.sha256(
            f'{row["source_sha256"]}:{row["source_structure"]}:{row["range_offset"]}:{row["metric"]}:V8'.encode()
        ).hexdigest(), axis=1)

    excluded = _review_accessions(protocol["development_reviews"])
    holdout = candidates.loc[
        ~candidates["accession_number"].astype(str).isin(excluded)
    ].copy() if not candidates.empty else candidates.copy()
    gate = protocol["review_gate"]
    review = select_stratified_review(holdout, gate["target_rows_per_metric"])
    if len(review) < gate["minimum_stratified_rows"] and not holdout.empty:
        indexes = set(review.index)
        for index in holdout.sort_values("review_priority").index:
            if len(indexes) >= min(gate["minimum_stratified_rows"], len(holdout)):
                break
            indexes.add(index)
        review = holdout.loc[sorted(indexes)].sort_values(["metric", "review_priority"]).copy()
    if not review.empty:
        review.insert(0, "review_id", [f"SG8-{number:04d}" for number in range(1, len(review) + 1)])
        review["review_decision"] = "PENDING"
        review["review_reason"] = ""
        review["reviewer"] = ""
        review["reviewed_at"] = ""
    ready = bool(
        len(review) >= gate["minimum_stratified_rows"]
        and review["ticker"].nunique() >= gate["minimum_distinct_tickers"]
    ) if not review.empty else False
    report = {
        "report_version": "herd-sec-guidance-v8-second-wave-validation-v1",
        "input_documents": int(pd.read_csv(corpus / "index.csv")["source_sha256"].nunique()),
        "v4_candidates": v4_report["v4_candidates"],
        "v5_candidates": len(v5),
        "v6_candidates": len(v6),
        "v7_candidates": len(v7),
        "v8_candidates": len(candidates),
        "v8_candidate_tickers": int(candidates["ticker"].nunique()) if not candidates.empty else 0,
        "development_accessions_excluded": len(excluded),
        "review_rows": len(review),
        "review_tickers": int(review["ticker"].nunique()) if not review.empty else 0,
        "review_sample_gate_ready": ready,
        "review_gate_passed": False,
        "ready_for_direction_preregistration": False,
        "next_decision": "COMPLETE_LOCKED_V8_SOURCE_REVIEW" if ready else "V8_INDEPENDENT_SAMPLE_COVERAGE_BLOCKED",
        "price_outcomes_observed": False,
        "operational_action_ratio": 0.0,
    }
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
