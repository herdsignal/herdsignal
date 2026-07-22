"""잠긴 V6 표본에 신규 기업 원문 후보만 결정론적으로 보충한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_block_extraction_v1 import load_aliases
from herd.sec_guidance_structure_parser_v4 import build as build_v4
from herd.sec_guidance_structure_parser_v5 import transform_candidate as transform_v5
from herd.sec_guidance_structure_parser_v6 import SourceLocator, transform_candidate as transform_v6


PROTOCOL = Path(__file__).with_suffix(".json")


def _verify(path: Path, expected: str) -> None:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(f"locked artifact hash mismatch: {path}")


def _development_accessions(protocol: dict) -> set[str]:
    excluded: set[str] = set()
    for path in protocol["development_reviews"]:
        excluded.update(pd.read_csv(path)["accession_number"].astype(str))
    return excluded


def _new_v6_candidates(protocol: dict) -> tuple[pd.DataFrame, dict]:
    corpora = [Path(path) for path in protocol["new_corpora"]]
    v4_protocol = {
        "development_reviews": protocol["development_reviews"],
        "review_gate": protocol["review_gate"],
    }
    v4, _, v4_report = build_v4(corpora, load_aliases(Path(protocol["alias_registry"])), v4_protocol)
    v5_rows = [item for _, row in v4.iterrows() if (item := transform_v5(row)) is not None]
    v5 = pd.DataFrame(v5_rows)
    locator_protocol = json.loads(Path("data/herd/sec_guidance_structure_parser_v6.json").read_text())
    locator = SourceLocator([*locator_protocol["source_corpora"], *(str(corpus) for corpus in corpora)])
    v6_rows = [item for _, row in v5.iterrows() if (item := transform_v6(row, locator)) is not None]
    v6 = pd.DataFrame(v6_rows)
    if not v6.empty:
        v6["review_priority"] = v6.apply(lambda row: hashlib.sha256(
            f'{row["source_sha256"]}:{row["source_structure"]}:{row["range_offset"]}:{row["metric"]}:V6_EXPANSION'.encode()
        ).hexdigest(), axis=1)
    return v6, v4_report


def _augment_locked_review(locked: pd.DataFrame, new: pd.DataFrame, gate: dict) -> pd.DataFrame:
    output = locked.copy()
    locked_tickers = set(output["ticker"].astype(str))
    new = new.loc[~new["ticker"].astype(str).isin(locked_tickers)].sort_values("review_priority").copy()
    chosen_indexes: list[int] = []
    # 먼저 각 신규 기업에서 한 건씩 고정해 기업 수 게이트를 충족한다.
    for _, group in new.groupby("ticker", sort=True):
        chosen_indexes.append(group.index[0])
    chosen_indexes.sort(key=lambda index: str(new.loc[index, "review_priority"]))
    chosen_indexes = chosen_indexes[:max(gate["minimum_new_candidate_tickers"], gate["minimum_distinct_tickers"] - len(locked_tickers))]
    chosen = set(chosen_indexes)
    # 이후 지표별 희소 후보를 우선하면서 80행까지 채운다.
    metric_counts = output["metric"].value_counts().to_dict()
    remaining = new.loc[~new.index.isin(chosen)].copy()
    remaining["metric_count"] = remaining["metric"].map(lambda metric: metric_counts.get(metric, 0))
    for index in remaining.sort_values(["metric_count", "review_priority"]).index:
        if len(output) + len(chosen) >= gate["minimum_stratified_rows"]:
            break
        chosen.add(index)
    additions = new.loc[sorted(chosen)].sort_values(["metric", "review_priority"]).copy()
    for column in ("review_id", "review_decision", "review_reason", "reviewer", "reviewed_at"):
        if column in additions:
            additions = additions.drop(columns=column)
    start = len(output) + 1
    additions.insert(0, "review_id", [f"SG6-{index:04d}" for index in range(start, start + len(additions))])
    additions["review_decision"] = "PENDING"
    additions["review_reason"] = ""
    additions["reviewer"] = ""
    additions["reviewed_at"] = ""
    return pd.concat([output, additions], ignore_index=True)


def build(protocol: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    cached_path = Path(protocol["cached_v6_candidates"])
    locked_path = Path(protocol["locked_v6_review"])
    _verify(cached_path, protocol["cached_v6_candidates_sha256"])
    _verify(locked_path, protocol["locked_v6_review_sha256"])
    cached = pd.read_csv(cached_path, dtype={"cik": str})
    locked = pd.read_csv(locked_path, dtype={"cik": str})
    new, v4_report = _new_v6_candidates(protocol)
    excluded = _development_accessions(protocol)
    new = new.loc[~new["accession_number"].astype(str).isin(excluded)].copy()
    identity = [
        "ticker", "accession_number", "metric", "fiscal_period", "accounting_basis", "metric_subtype",
        "unit", "lower_bound", "upper_bound", "source_structure", "range_offset",
    ]
    candidates = pd.concat([cached, new], ignore_index=True).drop_duplicates(identity)
    review = _augment_locked_review(locked, new, protocol["review_gate"])
    gate = protocol["review_gate"]
    new_tickers = set(new["ticker"].astype(str))
    locked_tickers = set(locked["ticker"].astype(str))
    review_new_tickers = set(review["ticker"].astype(str)) - locked_tickers
    ready = (
        len(review) >= gate["minimum_stratified_rows"]
        and review["ticker"].nunique() >= gate["minimum_distinct_tickers"]
        and len(review_new_tickers) >= gate["minimum_new_candidate_tickers"]
    )
    report = {
        "report_version": "herd-sec-guidance-v6-validation-expansion-v1",
        "locked_review_rows_preserved": len(locked),
        "locked_review_tickers": len(locked_tickers),
        "new_v4_candidates": v4_report["v4_candidates"],
        "new_v6_candidates": len(new),
        "new_v6_candidate_tickers": len(new_tickers),
        "expanded_review_rows": len(review),
        "expanded_review_tickers": int(review["ticker"].nunique()),
        "expanded_review_new_tickers": len(review_new_tickers),
        "review_sample_gate_ready": ready,
        "review_gate_passed": False,
        "ready_for_direction_preregistration": False,
        "next_decision": "COMPLETE_LOCKED_V6_SOURCE_REVIEW" if ready else "COLLECT_REMAINING_LOCKED_ISSUERS",
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
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    candidates, review, report = build(protocol)
    candidates.to_csv(args.candidates, index=False, float_format="%.12g", lineterminator="\n")
    review.to_csv(args.review, index=False, float_format="%.12g", lineterminator="\n")
    report["protocol_sha256"] = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    report["candidate_ledger_sha256"] = hashlib.sha256(args.candidates.read_bytes()).hexdigest()
    report["locked_review_sha256"] = hashlib.sha256(args.review.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
