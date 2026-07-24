"""V5 원문 오류 세 종류만 교정하는 정밀도 우선 V6 구조 결합기."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from pathlib import Path

import pandas as pd
from lxml import html

from herd.sec_guidance_block_extraction_v1 import select_stratified_review
from herd.sec_guidance_structure_parser_v5 import _context, _normalized_ranges, _same_bounds
from herd.sec_guidance_table_extraction_v1 import expand_table


PROTOCOL = Path(__file__).with_suffix(".json")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRIOR_COLUMN = re.compile(r"\b(?:prior|previous|original|initial)\b", re.I)
INITIAL_GUIDANCE = re.compile(r"\binitial\s+guidance\b", re.I)
UNCHANGED = re.compile(r"\bunchanged\b", re.I)
REPORTED_BASIS = re.compile(r"\bon\s+(?:a\s+)?reported\s+basis\b", re.I)
COMPACT_QUARTER = re.compile(r"\b([1-4])Q\s*(\d{2}|20\d{2})\b", re.I)
QUARTER_WORDS = {"first": 1, "second": 2, "third": 3, "fourth": 4}
FORWARD_QUARTER = re.compile(
    r"\bfor\s+(?:the\s+)?(first|second|third|fourth)\s+quarter(?:\s+of)?\s+(20\d{2})\b",
    re.I,
)
EXPECTED_YEAR = re.compile(r"\b(20\d{2})\s+[A-Za-z][A-Za-z -]{0,40}\s+is\s+expected\b", re.I)
REPORTING_HIGHLIGHTS = re.compile(r"\b(?:first|second|third|fourth)\s+quarter\s+20\d{2}\s+highlights\b", re.I)


class SourceLocator:
    """SEC 원문 SHA를 로컬 불변 코퍼스 파일에 연결한다."""

    def __init__(self, corpora: list[str]) -> None:
        self.paths: dict[str, Path] = {}
        for corpus_name in corpora:
            corpus = Path(corpus_name)
            if not corpus.is_absolute() and not corpus.exists():
                corpus = PROJECT_ROOT / corpus
            index = pd.read_csv(corpus / "index.csv", dtype=str)
            for _, row in index.iterrows():
                digest = str(row.get("source_sha256", ""))
                relative = str(row.get("path", ""))
                if digest and relative:
                    self.paths.setdefault(digest, corpus / relative)

    def read(self, digest: str) -> bytes | None:
        path = self.paths.get(str(digest))
        if path is None or not path.exists():
            return None
        with gzip.open(path, "rb") as source:
            return source.read()


def _target_table(row: pd.Series, locator: SourceLocator | None) -> list[list[str]] | None:
    if locator is None or str(row.get("source_structure")) != "HTML_TABLE_GRID" or pd.isna(row.get("table_index")):
        return None
    content = locator.read(str(row.get("source_sha256", "")))
    if content is None:
        return None
    try:
        tables = html.fromstring(content).xpath("//table")
        table = tables[int(row["table_index"])]
        return expand_table(table)
    except (IndexError, TypeError, ValueError):
        return None


def _table_context(grid: list[list[str]], row_index: int) -> str:
    return " | ".join(cell for row in grid[:row_index + 1] for cell in row if cell)


def _fix_table_binding(row: pd.Series, item: dict, locator: SourceLocator | None) -> dict | None:
    grid = _target_table(row, locator)
    row_index = int(row["row_index"]) if pd.notna(row.get("row_index")) else -1
    table_context = _table_context(grid, row_index) if grid is not None and row_index >= 0 else _context(row)
    if INITIAL_GUIDANCE.search(table_context):
        return None
    if PRIOR_COLUMN.search(str(row.get("header_path", ""))):
        row_cells = grid[row_index] if grid is not None and 0 <= row_index < len(grid) else []
        if not UNCHANGED.search(" | ".join(row_cells)):
            return None
    compact_periods = {
        f"Q{match.group(1)}-{('20' + match.group(2)) if len(match.group(2)) == 2 else match.group(2)}"
        for match in COMPACT_QUARTER.finditer(str(row.get("header_path", "")))
    }
    if len(compact_periods) > 1:
        return None
    if compact_periods:
        item["fiscal_period"] = next(iter(compact_periods))
    return item


def _fix_narrative_binding(row: pd.Series, item: dict) -> dict | None:
    context = _context(row)
    matching = [entry for entry in _normalized_ranges(context, str(row["unit"])) if _same_bounds(row, entry[1], entry[2])]
    if not matching:
        return None
    for match, _, _ in matching:
        if REPORTED_BASIS.match(context[match.end():match.end() + 45]):
            item["accounting_basis"] = "GAAP"
            break

    forward_periods = {
        f"Q{QUARTER_WORDS[match.group(1).lower()]}-{match.group(2)}"
        for match in FORWARD_QUARTER.finditer(context)
    }
    expected_years = {f"FY{match.group(1)}" for match in EXPECTED_YEAR.finditer(context)}
    explicit_periods = forward_periods | expected_years
    if len(explicit_periods) > 1:
        return None
    if explicit_periods:
        item["fiscal_period"] = next(iter(explicit_periods))
    elif REPORTING_HIGHLIGHTS.search(context):
        # 보고 분기 뒤에 연간 가이던스 범위가 오지만 전망 기간이 명시되지 않은 슬라이드는 보수적으로 제외한다.
        return None
    return item


def transform_candidate(row: pd.Series, locator: SourceLocator | None = None) -> dict | None:
    item = row.to_dict()
    if str(row.get("source_structure")) == "HTML_TABLE_GRID":
        item = _fix_table_binding(row, item, locator)
    else:
        item = _fix_narrative_binding(row, item)
    if item is None:
        return None
    item["candidate_status"] = "V6_THREE_RELATION_CORRECTED_NOT_SOURCE_REVIEWED"
    return item


def audit_v5_review(review_path: str, locator: SourceLocator) -> dict:
    reviewed = pd.read_csv(review_path, dtype={"cik": str})
    semantic = ("fiscal_period", "accounting_basis", "metric_subtype", "unit", "lower_bound", "upper_bound")
    invalid = reviewed.loc[reviewed["review_decision"].ne("VALID")]
    valid = reviewed.loc[reviewed["review_decision"].eq("VALID")]
    dropped = corrected = unchanged = 0
    for _, row in invalid.iterrows():
        transformed = transform_candidate(row, locator)
        if transformed is None:
            dropped += 1
        elif all(str(transformed[field]) == str(row[field]) for field in semantic):
            unchanged += 1
        else:
            corrected += 1
    valid_retained = sum(transform_candidate(row, locator) is not None for _, row in valid.iterrows())
    return {
        "v5_invalid_bindings_audited": int(len(invalid)),
        "v5_invalid_bindings_dropped": dropped,
        "v5_invalid_bindings_corrected": corrected,
        "v5_invalid_bindings_unchanged": unchanged,
        "v5_valid_bindings_audited": int(len(valid)),
        "v5_valid_bindings_retained": valid_retained,
        "v5_development_regression_passed": len(invalid) == 10 and unchanged == 0 and valid_retained == len(valid),
    }


def build(protocol: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    locator = SourceLocator(protocol["source_corpora"])
    source = pd.read_csv(protocol["v5_candidate_ledger"], dtype={"cik": str})
    candidates = pd.DataFrame([
        transformed for _, row in source.iterrows()
        if (transformed := transform_candidate(row, locator)) is not None
    ])
    if not candidates.empty:
        candidates["review_priority"] = candidates.apply(lambda row: hashlib.sha256(
            f'{row["source_sha256"]}:{row["source_structure"]}:{row["range_offset"]}:{row["metric"]}:V6'.encode()
        ).hexdigest(), axis=1)
    excluded = set()
    for path in protocol["development_reviews"]:
        excluded.update(pd.read_csv(path)["accession_number"].astype(str))
    holdout = candidates.loc[~candidates["accession_number"].astype(str).isin(excluded)].copy()
    review = select_stratified_review(holdout, protocol["review_gate"]["target_rows_per_metric"])
    minimum = protocol["review_gate"]["minimum_stratified_rows"]
    if len(review) < minimum and not holdout.empty:
        review = holdout.sort_values("review_priority").head(minimum).copy()
    if not review.empty:
        review.insert(0, "review_id", [f"SG6-{index:04d}" for index in range(1, len(review) + 1)])
        for column, default in [("review_decision", "PENDING"), ("review_reason", ""), ("reviewer", ""), ("reviewed_at", "")]:
            review[column] = default
    gate = protocol["review_gate"]
    ready = len(review) >= gate["minimum_stratified_rows"] and review["ticker"].nunique() >= gate["minimum_distinct_tickers"] if not review.empty else False
    report = {
        "report_version": "herd-sec-guidance-structure-parser-v6",
        "input_v5_candidates": len(source),
        "v6_candidates": len(candidates),
        "development_accessions_excluded": len(excluded),
        "fresh_holdout_candidates": len(holdout),
        "fresh_holdout_tickers": int(holdout["ticker"].nunique()) if not holdout.empty else 0,
        "fresh_review_rows": len(review),
        "fresh_review_tickers": int(review["ticker"].nunique()) if not review.empty else 0,
        "review_sample_gate_ready": ready,
        "review_gate_passed": False,
        "ready_for_direction_preregistration": False,
        "next_decision": "COMPLETE_FRESH_V6_SOURCE_REVIEW" if ready else "COLLECT_NEW_ISSUER_CORPUS_FOR_V6_REVIEW",
        "price_outcomes_observed": False,
        "operational_action_ratio": 0.0,
    }
    report.update(audit_v5_review(protocol["development_reviews"][-1], locator))
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
    report["v6_candidate_ledger_sha256"] = hashlib.sha256(args.candidates.read_bytes()).hexdigest()
    report["fresh_review_candidate_sha256"] = hashlib.sha256(args.review.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
