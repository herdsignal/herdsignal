"""범위마다 역할·지표·기간·회계기준·subtype을 결합하는 정밀도 우선 V3 파서."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import pandas as pd

from herd.sec_guidance_block_extraction_v1 import load_aliases, select_stratified_review
from herd.sec_guidance_structure_parser_v2 import (
    PROTOCOL as V2_PROTOCOL,
    QUARTER,
    QUARTER_PERIOD,
    FULL_YEAR_PERIOD,
    GUIDANCE_FOR_YEAR,
    parse_block_v2,
    _sentence_bounds,
)


PROTOCOL = Path(__file__).with_suffix(".json")
COMPARISON = re.compile(r"\b(?:compared\s+with|versus|vs\.?|year[- ]over[- ]year)\b", re.I)
ACTUAL_CONTEXT = re.compile(r"\b(?:actual|was|were|amounted|came\s+in|exceeded|below|reported|restat(?:e|ed|ement))\b", re.I)
FORWARD_CONTEXT = re.compile(r"\b(?:guidance|outlook|forecast|target|expects?|expected|projects?|projected|anticipates?)\b", re.I)
BARE_YEAR = re.compile(r"\b(20\d{2})\b")

METRIC_PATTERNS = [
    ("CASH_CAPEX", re.compile(r"\b(?:cash\s+capital expenditures|cash purchases of property and equipment)\b", re.I)),
    ("CAPEX", re.compile(r"\b(?:capital expenditures|capex)\b", re.I)),
    ("ADJUSTED_EBITDA", re.compile(r"\b(?:core\s+)?adjusted EBITDA(?:re)?\b", re.I)),
    ("CORE_FFO", re.compile(r"\bcore (?:FFO|funds from operations)\b", re.I)),
    ("AFFO", re.compile(r"\bAFFO\b", re.I)),
    ("FREE_CASH_FLOW", re.compile(r"\bfree cash flow\b", re.I)),
    ("OPERATING_INCOME", re.compile(r"\boperating income(?:\s*\(loss\))?\b", re.I)),
    ("MARGIN", re.compile(r"\b(?:operating|adjusted operating|commercial airplanes operating) margin\b", re.I)),
    ("EPS", re.compile(r"\b(?:diluted\s+)?(?:EPS|earnings per share)\b", re.I)),
    ("REVENUE", re.compile(r"\b(?:total |segment |property )?(?:revenue|net sales)\b", re.I)),
    ("UNSUPPORTED_DDA", re.compile(r"\bDD&A\b|\bdepreciation and amortization\b", re.I)),
    ("UNSUPPORTED_OPERATING_COST", re.compile(r"\b(?:adjusted )?operating costs?\b", re.I)),
    ("UNSUPPORTED_NET_EARNINGS", re.compile(r"\b(?:net earnings|net loss|corporate segment net loss)\b", re.I)),
]


def _period_mentions(text: str, end: int) -> list[tuple[int, str]]:
    mentions: list[tuple[int, str]] = []
    for match in QUARTER_PERIOD.finditer(text, 0, end):
        mentions.append((match.end(), f"Q{QUARTER[match.group(1).lower()]}-{match.group(2)}"))
    for match in FULL_YEAR_PERIOD.finditer(text, 0, end):
        mentions.append((match.end(), f"FY{match.group(1)}"))
    for match in GUIDANCE_FOR_YEAR.finditer(text, 0, end):
        mentions.append((match.end(), f"FY{match.group(1)}"))
    # "2015 Core FFO guidance"와 "2012 revenue guidance"처럼 연도가
    # 지표 앞에 오는 공시 문법. 같은 절에 forward 문맥이 있을 때만 허용한다.
    if not mentions and FORWARD_CONTEXT.search(text[:end]):
        for match in BARE_YEAR.finditer(text, 0, end):
            mentions.append((match.end(), f"FY{match.group(1)}"))
    return mentions


def _range_local_period(text: str, offset: int) -> str | None:
    start, _ = _sentence_bounds(text, offset)
    before = text[start:offset]
    mentions = _period_mentions(before, len(before))
    eligible = []
    for end, period in mentions:
        prefix = before[max(0, end - 70):end]
        if COMPARISON.search(prefix):
            continue
        eligible.append((end, period))
    return eligible[-1][1] if eligible else None


def _nearest_metric(text: str, offset: int) -> tuple[str, int, int] | None:
    start, _ = _sentence_bounds(text, offset)
    before = text[start:offset]
    mentions = []
    for metric, pattern in METRIC_PATTERNS:
        for match in pattern.finditer(before):
            mentions.append((match.end(), match.start(), metric))
    if not mentions:
        return None
    end, begin, metric = max(mentions)
    return metric, start + begin, start + end


def _range_local_basis(text: str, metric_start: int, offset: int, metric: str) -> str:
    local = text[max(0, metric_start - 45):offset]
    if re.search(r"\b(?:non[- ]GAAP|adjusted|core)\b", local, re.I):
        return "NON_GAAP"
    if re.search(r"\bGAAP\b|\breported basis\b", local, re.I):
        return "GAAP"
    if metric in {"CAPEX", "CASH_CAPEX"}:
        return "NOT_APPLICABLE"
    return "UNSPECIFIED"


def _semantic_context_is_current(text: str, offset: int) -> bool:
    start, _ = _sentence_bounds(text, offset)
    before = text[start:offset]
    comparison = list(COMPARISON.finditer(before))
    forward = list(FORWARD_CONTEXT.finditer(before))
    if not forward:
        return False
    if comparison and comparison[-1].end() > forward[-1].end():
        return False
    actual = list(ACTUAL_CONTEXT.finditer(before))
    return not actual or actual[-1].end() < forward[-1].end()


def _plausible_bounds(low: float, high: float) -> bool:
    if low > high:
        return False
    positive = [abs(value) for value in (low, high) if value != 0]
    return not positive or max(positive) / min(positive) <= 20.0


def _metric_subtype(text: str, metric_start: int, metric: str, current: str) -> str:
    if metric == "REVENUE":
        local = text[max(0, metric_start - 80):metric_start + 30]
        if re.search(r"\b(?:segment|defense, space\s*&\s*security|walmart u\.s\.)\b", local, re.I):
            return "SEGMENT_REVENUE"
    return current


def parse_block_v3(text: str, ticker: str, aliases) -> list[dict]:
    candidates = []
    for candidate in parse_block_v2(text, ticker, aliases):
        offset = int(candidate["range_offset"])
        nearest = _nearest_metric(text, offset)
        period = _range_local_period(text, offset)
        if nearest is None or period is None or not _semantic_context_is_current(text, offset):
            continue
        metric, metric_start, _ = nearest
        if metric.startswith("UNSUPPORTED_") or metric != candidate["metric"]:
            continue
        if candidate["range_role"] != "CURRENT_CANDIDATE" or candidate["semantic_role"] != "CURRENT_GUIDANCE_RANGE":
            continue
        if not _plausible_bounds(float(candidate["lower_bound"]), float(candidate["upper_bound"])):
            continue
        candidate = dict(candidate)
        candidate.update({
            "fiscal_period": period,
            "accounting_basis": _range_local_basis(text, metric_start, offset, metric),
            "metric_subtype": _metric_subtype(text, metric_start, metric, candidate["metric_subtype"]),
            "candidate_status": "V3_RANGE_BOUND_NOT_SOURCE_REVIEWED",
        })
        candidates.append(candidate)
    return candidates


def build_from_v2_ledger(ledger_path: Path, aliases, protocol: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """V2가 보존한 원문 블록을 한 번만 V3로 재판정한다."""
    ledger = pd.read_csv(ledger_path, dtype={"cik": str})
    identity = [
        "ticker", "cik", "accession_number", "accepted_at", "document_name",
        "source_url", "source_sha256", "source_kind", "block_path", "block_text",
    ]
    records = []
    for _, block in ledger[identity].drop_duplicates().iterrows():
        for candidate in parse_block_v3(block["block_text"], block["ticker"], aliases):
            records.append({**block.to_dict(), **candidate})
    candidates = pd.DataFrame(records)
    if not candidates.empty:
        candidates["review_priority"] = candidates.apply(lambda row: hashlib.sha256(
            f'{row["source_sha256"]}:{row["block_path"]}:{row["range_offset"]}:{row["metric"]}'.encode()
        ).hexdigest(), axis=1)
        candidates = candidates.drop_duplicates([
            "ticker", "accession_number", "block_path", "metric", "fiscal_period", "accounting_basis",
            "metric_subtype", "unit", "lower_bound", "upper_bound",
        ])

    excluded_accessions: set[str] = set()
    for path in protocol["development_reviews"]:
        excluded_accessions.update(pd.read_csv(path)["accession_number"].astype(str))
    holdout = candidates.loc[
        ~candidates["accession_number"].astype(str).isin(excluded_accessions)
    ].copy() if not candidates.empty else candidates.copy()
    review = select_stratified_review(holdout, protocol["review_gate"]["target_rows_per_metric"])
    if not review.empty:
        review.insert(0, "review_id", [f"SG3-{i:04d}" for i in range(1, len(review) + 1)])
        for column, default in [("review_decision", "PENDING"), ("review_reason", ""), ("reviewer", ""), ("reviewed_at", "")]:
            review[column] = default
    gate = protocol["review_gate"]
    ready = (
        len(review) >= gate["minimum_stratified_rows"]
        and review["ticker"].nunique() >= gate["minimum_distinct_tickers"]
    ) if not review.empty else False
    return candidates, review, {
        "report_version": "herd-sec-guidance-structure-parser-v3",
        "input_v2_ledger": str(ledger_path),
        "input_v2_ledger_sha256": hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
        "development_accessions_excluded": len(excluded_accessions),
        "v3_candidates": len(candidates),
        "v3_candidate_tickers": int(candidates["ticker"].nunique()) if not candidates.empty else 0,
        "fresh_holdout_candidates": len(holdout),
        "fresh_holdout_tickers": int(holdout["ticker"].nunique()) if not holdout.empty else 0,
        "fresh_review_rows": len(review),
        "fresh_review_tickers": int(review["ticker"].nunique()) if not review.empty else 0,
        "review_sample_gate_ready": ready,
        "review_gate_passed": False,
        "source_qualified_revision_pairs": 0,
        "ready_for_direction_preregistration": False,
        "next_decision": "COMPLETE_FRESH_V3_SOURCE_REVIEW" if ready else "FRESH_REVIEW_SAMPLE_COVERAGE_BLOCKED",
        "price_outcomes_observed": False,
        "operational_action_ratio": 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    aliases = load_aliases(Path(protocol["alias_registry"]))
    candidates, review, report = build_from_v2_ledger(
        Path(protocol["v2_candidate_ledger"]), aliases, protocol,
    )
    candidates.to_csv(args.candidates, index=False, float_format="%.12g", lineterminator="\n")
    review.to_csv(args.review, index=False, float_format="%.12g", lineterminator="\n")
    report["protocol_sha256"] = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    report["v2_protocol_sha256"] = hashlib.sha256(V2_PROTOCOL.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
