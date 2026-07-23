"""신규 기업 코퍼스를 V4→V10으로 재생해 최종 독립 표본을 잠근다."""

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
from herd.sec_guidance_structure_parser_v9 import transform_candidate as transform_v9
from herd.sec_guidance_structure_parser_v10 import transform_candidate as transform_v10


PROTOCOL = Path(__file__).with_suffix(".json")
IDENTITY = [
    "source_sha256", "metric", "fiscal_period", "accounting_basis", "metric_subtype",
    "unit", "lower_bound", "upper_bound", "source_structure", "range_offset",
]


def _transform(frame: pd.DataFrame, transform, *args) -> pd.DataFrame:
    rows = [item for _, row in frame.iterrows() if (item := transform(row, *args)) is not None]
    return pd.DataFrame(rows)


def _integrity(corpus: Path) -> dict:
    manifest = json.loads((corpus / "manifest.json").read_text())
    index = pd.read_csv(corpus / "index.csv")
    requested = int(manifest["filings_requested"])
    collected = int(manifest["filings_collected"])
    accessions = int(index["accession_number"].nunique())
    failures = len(manifest.get("failures", []))
    return {
        "filings_requested": requested,
        "filings_collected": collected,
        "indexed_accessions": accessions,
        "input_documents": int(index["source_sha256"].nunique()),
        "collection_failures": failures,
        "corpus_integrity_passed": requested == collected == accessions and failures == 0,
    }


def build(protocol: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    corpus = Path(protocol["corpus"])
    integrity = _integrity(corpus)
    if not integrity["corpus_integrity_passed"]:
        raise ValueError("V10 final corpus integrity gate failed")
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
    v8 = _transform(v7, transform_v8)
    v9 = _transform(v8, transform_v9)
    expansion = _transform(v9, transform_v10)
    if not expansion.empty:
        expansion["v10_candidate_origin"] = "FINAL_EXPANSION"
    base = pd.read_csv(protocol["base_candidates"], dtype={"cik": str})
    base["v10_candidate_origin"] = "PRIOR_UNREVIEWED_POOL"
    candidates = pd.concat([base, expansion], ignore_index=True).drop_duplicates(IDENTITY)
    candidates["review_priority"] = candidates.apply(
        lambda row: hashlib.sha256(
            f'{row["source_sha256"]}:{row["source_structure"]}:'
            f'{row["range_offset"]}:{row["metric"]}:V10-FINAL'.encode()
        ).hexdigest(),
        axis=1,
    )
    excluded: set[str] = set()
    for path in protocol["development_reviews"]:
        excluded.update(pd.read_csv(path)["accession_number"].astype(str))
    holdout = candidates.loc[
        ~candidates["accession_number"].astype(str).isin(excluded)
    ].copy()
    expansion_holdout = holdout.loc[holdout["v10_candidate_origin"].eq("FINAL_EXPANSION")]
    gate = protocol["review_gate"]
    stratified = select_stratified_review(holdout, gate["target_rows_per_metric"])
    ranked = holdout.sort_values("review_priority")
    coverage_seed = ranked.groupby("ticker", group_keys=False).head(1).sort_values("review_priority").head(
        gate["minimum_distinct_tickers"]
    )
    expansion_seed = (
        expansion_holdout.sort_values("review_priority").groupby("ticker", group_keys=False).head(1)
        .sort_values("review_priority").head(gate["minimum_new_expansion_tickers"])
    )
    seeds = set(coverage_seed.index) | set(expansion_seed.index)
    selected = set(stratified.index) | seeds
    target = min(gate["minimum_stratified_rows"], len(holdout))
    for index in ranked.index:
        if len(selected) >= target:
            break
        selected.add(index)
    if len(selected) > target:
        remainder = [index for index in ranked.index if index in selected and index not in seeds]
        selected = seeds | set(remainder[:max(0, target - len(seeds))])
    review = holdout.loc[sorted(selected)].sort_values(["metric", "review_priority"]).copy()
    if not review.empty:
        review.insert(0, "review_id", [f"SG10F-{number:04d}" for number in range(1, len(review) + 1)])
        review["review_decision"] = "PENDING"
        review["review_reason"] = ""
        review["reviewer"] = ""
        review["reviewed_at"] = ""
    expansion_review_tickers = int(
        review.loc[review["v10_candidate_origin"].eq("FINAL_EXPANSION"), "ticker"].nunique()
    ) if not review.empty else 0
    ready = bool(
        len(review) >= gate["minimum_stratified_rows"]
        and review["ticker"].nunique() >= gate["minimum_distinct_tickers"]
        and expansion_review_tickers >= gate["minimum_new_expansion_tickers"]
    ) if not review.empty else False
    report = {
        "report_version": "herd-sec-guidance-v10-final-validation-v1",
        **integrity,
        "v4_candidates": v4_report["v4_candidates"],
        "v5_candidates": len(v5),
        "v6_candidates": len(v6),
        "v7_candidates": len(v7),
        "v8_candidates": len(v8),
        "v9_candidates": len(v9),
        "new_v10_candidates": len(expansion),
        "new_v10_candidate_tickers": int(expansion["ticker"].nunique()) if not expansion.empty else 0,
        "fresh_holdout_candidates": len(holdout),
        "fresh_holdout_tickers": int(holdout["ticker"].nunique()),
        "review_rows": len(review),
        "review_tickers": int(review["ticker"].nunique()) if not review.empty else 0,
        "review_expansion_tickers": expansion_review_tickers,
        "review_sample_gate_ready": ready,
        "review_gate_passed": False,
        "ready_for_direction_preregistration": False,
        "next_decision": "COMPLETE_LOCKED_V10_FINAL_SOURCE_REVIEW" if ready else "STOP_ITERATIVE_PARSER_VERSIONING",
        "price_outcomes_observed": False,
        "operational_action_ratio": 0.0,
    }
    return expansion, review, report


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
