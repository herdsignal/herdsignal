"""V4에서 확인된 여섯 문법 관계만 교정하는 정밀도 우선 V5 파서."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import pandas as pd

from herd.sec_guidance_block_extraction_v1 import select_stratified_review
from herd.sec_guidance_normalization_v1 import SCALE_FACTOR, _number


PROTOCOL = Path(__file__).with_suffix(".json")
NUMBER = r"(?P<{name}>\(?-?[$€£]?\s*\d{{1,3}}(?:,\d{{3}})*(?:\.\d+)?\)?)"
SCALE = r"(?P<{name}>billion|million|thousand|%|percent|cents|per share)?"
STRICT_RANGE = re.compile(
    NUMBER.format(name="low") + r"\s*" + SCALE.format(name="low_scale")
    + r"\s*(?:to|through|[-–—])\s*"
    + NUMBER.format(name="high") + r"\s*" + SCALE.format(name="high_scale"),
    re.I,
)
COMPACT_QUARTER = re.compile(r"\bQ([1-4])\s*(?:Fiscal\s+Year|FY)\s*(20\d{2}|\d{2})\b", re.I)
MULTI_BASIS = re.compile(r"\bboth\s+(?:a\s+)?reported\s+and\s+non[- ]GAAP\s+basis\b", re.I)
EX_PENSION_MTM = re.compile(r"\bex[- ]pension\s+MTM\b", re.I)
AFTER_DIVIDENDS = re.compile(r"\bfree cash flow after dividends\b", re.I)
AMBIGUOUS_Q_AND_FY = re.compile(r"\bfirst quarter\s+and\s+fiscal year\b", re.I)


def _context(row: pd.Series) -> str:
    return " | ".join(
        str(row.get(field, ""))
        for field in ("header_path", "row_header", "source_excerpt")
        if pd.notna(row.get(field)) and str(row.get(field)).strip()
    )


def _normalized_ranges(text: str, unit: str) -> list[tuple[re.Match, float, float]]:
    output = []
    for match in STRICT_RANGE.finditer(text):
        low, high = _number(match.group("low")), _number(match.group("high"))
        low_scale = (match.group("low_scale") or "").lower()
        high_scale = (match.group("high_scale") or "").lower()
        scale = high_scale or low_scale
        if unit == "USD":
            if scale not in SCALE_FACTOR:
                continue
            low, high = low * SCALE_FACTOR[scale], high * SCALE_FACTOR[scale]
        elif unit == "USD_PER_SHARE":
            if scale == "cents":
                low, high = low * 0.01, high * 0.01
            elif scale in SCALE_FACTOR:
                continue
        elif unit == "PERCENT":
            if scale not in {"%", "percent"} and "%" not in match.group(0):
                continue
        output.append((match, min(low, high), max(low, high)))
    return output


def _same_bounds(row: pd.Series, low: float, high: float) -> bool:
    low_tolerance = 1e-8 * max(1.0, abs(float(row["lower_bound"])))
    high_tolerance = 1e-8 * max(1.0, abs(float(row["upper_bound"])))
    return abs(float(row["lower_bound"]) - low) <= low_tolerance and abs(float(row["upper_bound"]) - high) <= high_tolerance


def _is_prior_range(text: str, match: re.Match) -> bool:
    before = text[max(0, match.start() - 90):match.start()]
    after = text[match.end():min(len(text), match.end() + 70)]
    if re.search(r"\b(?:up\s+from|from|initial(?:ly)?(?:\s+\w+){0,3}|previous(?:ly)?(?:\s+\w+){0,3})\s*$", before, re.I):
        return True
    if re.match(r"^\s*to\s+(?:a\s+)?(?:new\s+)?(?:range\s+of\s+)?[$€£]?\d", after, re.I):
        return True
    return False


def transform_candidate(row: pd.Series) -> dict | None:
    item = row.to_dict()
    context = _context(row)
    if MULTI_BASIS.search(context) or AMBIGUOUS_Q_AND_FY.search(context):
        return None
    matching_ranges = [entry for entry in _normalized_ranges(context, str(row["unit"])) if _same_bounds(row, entry[1], entry[2])]
    if not matching_ranges or all(_is_prior_range(context, match) for match, _, _ in matching_ranges):
        return None
    compact = list(COMPACT_QUARTER.finditer(context))
    if compact:
        periods = {
            f"Q{match.group(1)}-{('20' + match.group(2)) if len(match.group(2)) == 2 else match.group(2)}"
            for match in compact
        }
        if len(periods) != 1:
            return None
        item["fiscal_period"] = next(iter(periods))
    if EX_PENSION_MTM.search(context):
        item["accounting_basis"] = "NON_GAAP"
    if item["metric"] == "FREE_CASH_FLOW" and AFTER_DIVIDENDS.search(context):
        item["metric_subtype"] = "AFTER_DIVIDENDS"
    item["candidate_status"] = "V5_SIX_RELATION_CORRECTED_NOT_SOURCE_REVIEWED"
    return item


def audit_v4_nonvalid_bindings(review_path: str) -> dict:
    """V4 검수에서 확인된 오결합이 동일한 의미 객체로 잔존하는지 검사한다."""
    reviewed = pd.read_csv(review_path, dtype={"cik": str})
    nonvalid = reviewed.loc[reviewed["review_decision"].isin(["INVALID", "AMBIGUOUS"])]
    semantic_fields = (
        "fiscal_period", "accounting_basis", "metric_subtype", "unit",
        "lower_bound", "upper_bound",
    )
    dropped = corrected = unchanged = 0
    for _, row in nonvalid.iterrows():
        transformed = transform_candidate(row)
        if transformed is None:
            dropped += 1
            continue
        if all(str(transformed[field]) == str(row[field]) for field in semantic_fields):
            unchanged += 1
        else:
            corrected += 1
    return {
        "v4_nonvalid_bindings_audited": len(nonvalid),
        "v4_nonvalid_bindings_dropped": dropped,
        "v4_nonvalid_bindings_corrected": corrected,
        "v4_nonvalid_bindings_unchanged": unchanged,
        "v4_development_regression_passed": len(nonvalid) > 0 and unchanged == 0,
    }


def build(protocol: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    source = pd.read_csv(protocol["v4_candidate_ledger"], dtype={"cik": str})
    transformed = [item for _, row in source.iterrows() if (item := transform_candidate(row)) is not None]
    candidates = pd.DataFrame(transformed)
    if not candidates.empty:
        candidates["review_priority"] = candidates.apply(lambda row: hashlib.sha256(
            f'{row["source_sha256"]}:{row["source_structure"]}:{row["range_offset"]}:{row["metric"]}:V5'.encode()
        ).hexdigest(), axis=1)
        candidates = candidates.drop_duplicates([
            "ticker", "accession_number", "metric", "fiscal_period", "accounting_basis", "metric_subtype",
            "unit", "lower_bound", "upper_bound", "source_structure", "range_offset",
        ])
    excluded = set()
    for path in protocol["development_reviews"]:
        excluded.update(pd.read_csv(path)["accession_number"].astype(str))
    holdout = candidates.loc[~candidates["accession_number"].astype(str).isin(excluded)].copy() if not candidates.empty else candidates.copy()
    review = select_stratified_review(holdout, protocol["review_gate"]["target_rows_per_metric"])
    minimum = protocol["review_gate"]["minimum_stratified_rows"]
    if len(review) < minimum and not holdout.empty:
        selected = set(review.index)
        for index in holdout.sort_values("review_priority").index:
            if len(selected) >= min(minimum, len(holdout)):
                break
            selected.add(index)
        review = holdout.loc[sorted(selected)].sort_values(["metric", "review_priority"]).copy()
    if not review.empty:
        review.insert(0, "review_id", [f"SG5-{index:04d}" for index in range(1, len(review) + 1)])
        for column, default in [("review_decision", "PENDING"), ("review_reason", ""), ("reviewer", ""), ("reviewed_at", "")]:
            review[column] = default
    gate = protocol["review_gate"]
    ready = len(review) >= gate["minimum_stratified_rows"] and review["ticker"].nunique() >= gate["minimum_distinct_tickers"] if not review.empty else False
    report = {
        "report_version": "herd-sec-guidance-structure-parser-v5",
        "input_v4_candidates": len(source),
        "v5_candidates": len(candidates),
        "v5_candidate_tickers": int(candidates["ticker"].nunique()) if not candidates.empty else 0,
        "development_accessions_excluded": len(excluded),
        "fresh_holdout_candidates": len(holdout),
        "fresh_holdout_tickers": int(holdout["ticker"].nunique()) if not holdout.empty else 0,
        "fresh_review_rows": len(review),
        "fresh_review_tickers": int(review["ticker"].nunique()) if not review.empty else 0,
        "review_sample_gate_ready": ready,
        "review_gate_passed": False,
        "source_qualified_revision_pairs": 0,
        "ready_for_direction_preregistration": False,
        "next_decision": "COMPLETE_FRESH_V5_SOURCE_REVIEW" if ready else "FRESH_V5_REVIEW_SAMPLE_COVERAGE_BLOCKED",
        "price_outcomes_observed": False,
        "operational_action_ratio": 0.0,
    }
    report.update(audit_v4_nonvalid_bindings(protocol["development_reviews"][-1]))
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
    report["v4_candidate_ledger_sha256"] = hashlib.sha256(Path(protocol["v4_candidate_ledger"]).read_bytes()).hexdigest()
    report["v5_candidate_ledger_sha256"] = hashlib.sha256(args.candidates.read_bytes()).hexdigest()
    report["fresh_review_candidate_sha256"] = hashlib.sha256(args.review.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
