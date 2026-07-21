"""SEC 가이던스의 병렬 관계·의미 역할·기간·기준·subtype을 구조적으로 파싱한다."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from pathlib import Path

import pandas as pd

from herd.sec_guidance_block_extraction_v1 import (
    Alias,
    _nearest_alias,
    _normalize,
    load_aliases,
    select_stratified_review,
    structured_blocks,
)
from herd.sec_guidance_normalization_v1 import RANGE
from herd.sec_8k_guidance_coverage_v1 import GUIDANCE


PROTOCOL = Path(__file__).with_suffix(".json")
QUARTER = {"first": "1", "second": "2", "third": "3", "fourth": "4"}
QUARTER_PERIOD = re.compile(
    r"\b(first|second|third|fourth)\s+quarter(?:\s+of)?(?:\s+fiscal(?:\s+year)?)?\s+(20\d{2})\b", re.I,
)
FULL_YEAR_PERIOD = re.compile(r"\b(?:full[- ]year|fiscal\s+year|FY)\s*(20\d{2})\b", re.I)
GUIDANCE_FOR_YEAR = re.compile(r"\bguidance\s+for\s+(20\d{2})\b", re.I)
RELATION_METRICS = [
    ("ADJUSTED_EBITDA", re.compile(r"\b(?:core\s+)?adjusted EBITDA(?:re)?\b", re.I)),
    ("CORE_FFO", re.compile(r"\bcore (?:FFO|funds from operations)\b", re.I)),
    ("AFFO", re.compile(r"\b(?:consolidated\s+)?AFFO(?: attributable to [^,;]+)?\b", re.I)),
    ("REVENUE", re.compile(r"\b(?:total )?(?:property )?(?:revenue|net sales)\b", re.I)),
    ("NET_INCOME", re.compile(r"\bnet income(?: attributable to [^,;]+)?\b", re.I)),
    ("LEASING_REVENUE", re.compile(r"\b(?:expected )?leasing revenues?\b", re.I)),
    ("EPS", re.compile(r"\b(?:adjusted |GAAP |non-GAAP )?(?:diluted )?(?:EPS|earnings per share)\b", re.I)),
    ("OPERATING_INCOME", re.compile(r"\boperating income\b", re.I)),
    ("FREE_CASH_FLOW", re.compile(r"\bfree cash flow\b", re.I)),
]
ELIGIBLE = {
    "REVENUE", "EPS", "MARGIN", "OPERATING_INCOME", "FREE_CASH_FLOW", "CAPEX",
    "ADJUSTED_EBITDA", "CORE_FFO", "AFFO", "ORGANIC_REVENUE_GROWTH", "CASH_CAPEX",
}


def _sentence_bounds(text: str, offset: int) -> tuple[int, int]:
    boundaries = list(re.finditer(r"(?<!\d)[.;](?=\s+[A-Z])|\n", text))
    starts = [match.end() for match in boundaries if match.end() <= offset]
    ends = [match.start() + 1 for match in boundaries if match.start() >= offset]
    return (max(starts) if starts else 0), (min(ends) if ends else len(text))


def _relation_map(text: str) -> dict[int, str]:
    """respectively 절에서 각 RANGE 시작 위치를 같은 순서의 지표에 연결한다."""
    mapped: dict[int, str] = {}
    for marker in re.finditer(r"\brespectively\b", text, re.I):
        start, _ = _sentence_bounds(text, marker.start())
        clause = text[start:marker.end()]
        metrics = []
        occupied: list[tuple[int, int]] = []
        mentions = []
        for metric, pattern in RELATION_METRICS:
            for match in pattern.finditer(clause):
                mentions.append((match.start(), -(match.end() - match.start()), match.end(), metric))
        for begin, _, end, metric in sorted(mentions):
            if any(begin < used_end and end > used_begin for used_begin, used_end in occupied):
                continue
            occupied.append((begin, end))
            metrics.append((begin, metric))
        metrics = [metric for _, metric in sorted(metrics)]
        ranges = list(RANGE.finditer(clause))
        if len(metrics) == len(ranges) and len(ranges) >= 2:
            mapped.update({start + match.start(): metric for metric, match in zip(metrics, ranges)})
    return mapped


def _semantic_role(text: str, match: re.Match) -> str:
    start, end = _sentence_bounds(text, match.start())
    sentence = text[start:end]
    local_before = text[max(start, match.start() - 180):match.start()]
    sentence_before = text[start:match.start()]
    if re.search(r"\bmidpoints?\b[^.;]*\bby\b", sentence_before, re.I):
        return "MIDPOINT_CHANGE"
    if re.search(r"\b(?:impact|outperformance|headwind|tailwind|reduction|charge)s?\b", sentence, re.I) and not re.search(
        r"\b(?:guidance|outlook|forecast|target)\s+(?:is|of|to|range)|\bexpected to be\b", local_before, re.I
    ):
        return "IMPACT_AMOUNT"
    if re.search(r"\b(?:includes?|including)\b[^.;]{0,100}$", local_before, re.I):
        return "COMPONENT_AMOUNT"
    if re.search(r"\b(?:adjustments?|reconciliation)\b[^.;]*$", sentence_before, re.I) and not re.search(
        r"\b(?:range|between|from)\b[^.;]{0,100}$", local_before, re.I
    ):
        return "COMPONENT_AMOUNT"
    if re.search(r"\b(?:came in|was|were)\s+(?:within|at)\s+the\s+guidance\b", local_before, re.I):
        return "HISTORICAL_REFERENCE"
    return "CURRENT_GUIDANCE_RANGE"


def _has_guidance_context(text: str, match: re.Match) -> bool:
    """범위가 실제 전망 문맥에 속할 때만 구조 파싱 대상으로 인정한다."""
    start, end = _sentence_bounds(text, match.start())
    sentence = text[start:end]
    if GUIDANCE.search(sentence):
        return True
    # 표/목록에서는 가이던스 머리글이 바로 앞 행에 있고 지표 행에는 생략될 수 있다.
    preceding = text[max(0, start - 240):start]
    return bool(GUIDANCE.search(preceding))


def _range_role(text: str, matches: list[re.Match], index: int) -> str:
    match = matches[index]
    before = text[max(0, match.start() - 100):match.start()]
    if re.search(r"\b(?:prior|previous(?:ly)?)\b[^.;:]{0,90}$", before, re.I):
        return "PRIOR_REFERENCE"
    if re.search(r"\bfrom\s*$", before, re.I):
        return "PRIOR_REFERENCE"
    if index + 1 < len(matches):
        between = text[match.end():matches[index + 1].start()]
        if re.search(r"^\s*to\s*$", between, re.I) and re.search(r"\bfrom\b[^.;]{0,100}$", before, re.I):
            return "PRIOR_REFERENCE"
    return "CURRENT_CANDIDATE"


def _period_for_range(text: str, match: re.Match, alias_end: int) -> str | None:
    window_start = max(0, alias_end - 320)
    window_end = min(len(text), alias_end + 120)
    window = text[window_start:window_end]
    candidates = []
    for period_match in QUARTER_PERIOD.finditer(window):
        candidates.append((abs(window_start + period_match.end() - alias_end), 0, f"Q{QUARTER[period_match.group(1).lower()]}-{period_match.group(2)}"))
    for period_match in FULL_YEAR_PERIOD.finditer(window):
        candidates.append((abs(window_start + period_match.end() - alias_end), 1, f"FY{period_match.group(1)}"))
    for period_match in GUIDANCE_FOR_YEAR.finditer(window):
        candidates.append((abs(window_start + period_match.end() - alias_end), 1, f"FY{period_match.group(1)}"))
    return min(candidates)[2] if candidates else None


def _basis_for_range(text: str, match: re.Match, alias: Alias) -> str:
    local_before = text[max(0, match.start() - 100):match.start()]
    local_after = text[match.end():min(len(text), match.end() + 55)]
    candidates = []
    for pattern, basis in [(re.compile(r"\bnon[- ]GAAP\b", re.I), "NON_GAAP"), (re.compile(r"\bGAAP\b|\breported basis\b", re.I), "GAAP")]:
        for basis_match in pattern.finditer(local_after):
            candidates.append((basis_match.start(), basis))
        for basis_match in pattern.finditer(local_before[-60:]):
            candidates.append((len(local_before[-60:]) - basis_match.end() + 20, basis))
    if candidates:
        return min(candidates)[1]
    return alias.accounting_basis


def _cash_capex_subtype(text: str, match: re.Match, metric: str) -> str:
    if metric != "CASH_CAPEX":
        return "NOT_APPLICABLE"
    context = text[max(0, match.start() - 180):match.start()]
    mentions = list(re.finditer(r"\b(including|excluding)\s+capitalized interest\b", context, re.I))
    if not mentions:
        return "UNSPECIFIED"
    return "INCLUDING_CAPITALIZED_INTEREST" if mentions[-1].group(1).lower() == "including" else "EXCLUDING_CAPITALIZED_INTEREST"


def parse_block_v2(text: str, ticker: str, aliases: list[Alias]) -> list[dict]:
    matches = list(RANGE.finditer(text))
    relations = _relation_map(text)
    output = []
    for index, match in enumerate(matches):
        if not _has_guidance_context(text, match):
            continue
        alias_match = _nearest_alias(text[:match.start()], ticker, aliases)
        if alias_match is None:
            continue
        alias, distance = alias_match
        if distance > 180:
            continue
        relation_metric = relations.get(match.start())
        metric = relation_metric or alias.canonical_metric
        if metric not in ELIGIBLE:
            continue
        if relation_metric and relation_metric != alias.canonical_metric:
            replacements = [candidate for candidate in aliases if candidate.canonical_metric == relation_metric and (candidate.ticker_scope is None or ticker in candidate.ticker_scope)]
            if not replacements:
                continue
            alias = max(replacements, key=lambda candidate: len(candidate.alias_pattern))
        role = _semantic_role(text, match)
        range_role = _range_role(text, matches, index)
        try:
            normalized = _normalize(match, alias, text[match.end():])
        except ValueError:
            normalized = None
        period = _period_for_range(text, match, match.start() - distance)
        if normalized is None or period is None:
            continue
        low, high, unit = normalized
        subtype = _cash_capex_subtype(text, match, metric)
        if metric == "CASH_CAPEX" and subtype != "UNSPECIFIED" and role == "COMPONENT_AMOUNT":
            role = "CURRENT_GUIDANCE_RANGE"
        output.append({
            "metric": metric,
            "fiscal_period": period,
            "accounting_basis": _basis_for_range(text, match, alias),
            "metric_subtype": subtype,
            "unit": unit,
            "lower_bound": low,
            "upper_bound": high,
            "midpoint": (low + high) / 2,
            "range_offset": match.start(),
            "range_role": range_role,
            "semantic_role": role,
            "candidate_status": "V2_STRUCTURE_PARSED_NOT_SOURCE_REVIEWED",
        })
    return output


def build(corpus: Path, aliases: list[Alias], protocol: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    source_index = pd.read_csv(corpus / "index.csv", dtype={"cik": str})
    development = pd.read_csv(protocol["development_review"])
    excluded_accessions = set(development["accession_number"].astype(str))
    records = []
    for _, source in source_index.iterrows():
        with gzip.open(corpus / source["path"], "rb") as stream:
            content = stream.read()
        for block in structured_blocks(content):
            for candidate in parse_block_v2(block["block_text"], source["ticker"], aliases):
                if candidate["semantic_role"] != "CURRENT_GUIDANCE_RANGE" or candidate["range_role"] != "CURRENT_CANDIDATE":
                    continue
                records.append({
                    "ticker": source["ticker"], "cik": source["cik"],
                    "accession_number": source["accession_number"], "accepted_at": source["accepted_at"],
                    "document_name": source["document_name"], "source_url": source["source_url"],
                    "source_sha256": source["source_sha256"], **block, **candidate,
                })
    candidates = pd.DataFrame(records)
    if not candidates.empty:
        candidates["review_priority"] = candidates.apply(lambda row: hashlib.sha256(
            f'{row["source_sha256"]}:{row["block_path"]}:{row["range_offset"]}:{row["metric"]}'.encode()
        ).hexdigest(), axis=1)
        candidates = candidates.drop_duplicates([
            "ticker", "accession_number", "block_path", "metric", "fiscal_period", "accounting_basis",
            "metric_subtype", "unit", "lower_bound", "upper_bound",
        ])
    holdout = candidates.loc[~candidates["accession_number"].astype(str).isin(excluded_accessions)].copy() if not candidates.empty else candidates.copy()
    review = select_stratified_review(holdout, protocol["review_gate"]["target_rows_per_metric"])
    if not review.empty:
        review.insert(0, "review_id", [f"SG2-{i:04d}" for i in range(1, len(review) + 1)])
        for column, default in [("review_decision", "PENDING"), ("review_reason", ""), ("reviewer", ""), ("reviewed_at", "")]:
            review[column] = default
    gate = protocol["review_gate"]
    ready = len(review) >= gate["minimum_stratified_rows"] and review["ticker"].nunique() >= gate["minimum_distinct_tickers"] if not review.empty else False
    report = {
        "report_version": "herd-sec-guidance-structure-parser-v2",
        "development_accessions_excluded": len(excluded_accessions),
        "v2_candidates": len(candidates),
        "v2_candidate_tickers": int(candidates["ticker"].nunique()) if not candidates.empty else 0,
        "fresh_holdout_candidates": len(holdout),
        "fresh_holdout_tickers": int(holdout["ticker"].nunique()) if not holdout.empty else 0,
        "fresh_review_rows": len(review),
        "fresh_review_tickers": int(review["ticker"].nunique()) if not review.empty else 0,
        "review_sample_gate_ready": ready,
        "review_gate_passed": False,
        "source_qualified_revision_pairs": 0,
        "ready_for_direction_preregistration": False,
        "next_decision": "COMPLETE_FRESH_V2_SOURCE_REVIEW" if ready else "FRESH_REVIEW_SAMPLE_COVERAGE_BLOCKED",
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
    aliases = load_aliases(Path(protocol["alias_registry"]))
    candidates, review, report = build(Path(protocol["corpus"]), aliases, protocol)
    candidates.to_csv(args.candidates, index=False, float_format="%.12g", lineterminator="\n")
    review.to_csv(args.review, index=False, float_format="%.12g", lineterminator="\n")
    report["protocol_sha256"] = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
