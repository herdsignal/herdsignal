"""표 계층과 문장 역할을 보존해 SEC 가이던스 범위를 원자적으로 결합한다."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
from lxml import etree, html

from herd.sec_8k_guidance_coverage_v1 import GUIDANCE
from herd.sec_guidance_block_extraction_v1 import Alias, load_aliases, select_stratified_review, structured_blocks
from herd.sec_guidance_normalization_v1 import RANGE
from herd.sec_guidance_structure_parser_v2 import _sentence_bounds, parse_block_v2
from herd.sec_guidance_structure_parser_v3 import (
    ACTUAL_CONTEXT,
    COMPARISON,
    FORWARD_CONTEXT,
    _metric_subtype,
    _nearest_metric,
    _plausible_bounds,
    _range_local_basis,
    _range_local_period,
    _semantic_context_is_current,
)
from herd.sec_guidance_table_extraction_v1 import expand_table


PROTOCOL = Path(__file__).with_suffix(".json")
CURRENT_HEADER = re.compile(r"\b(?:current|updated|revised|new|now|raises?|lowered?)\b", re.I)
PRIOR_HEADER = re.compile(r"\b(?:prior|previous|former|original)\b", re.I)
HISTORICAL_RECAP = re.compile(
    r"\b(?:historical|previously issued|had (?:expected|forecast)|was within|actual|estimated actual)\b", re.I,
)
REPORTING_CONTEXT = re.compile(r"\b(?:results?|reported|ended)\b", re.I)
USE_OF_CASH = re.compile(r"\b(?:use|uses) of cash\b", re.I)
AS_OF_DATE = re.compile(
    r"\b(?:as of\s+)?(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+"
    r"(\d{1,2}),?\s+(20\d{2})\b", re.I,
)
MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
NARRATIVE_SOURCE_KINDS = {"ASCII", "ASCII_PARSE_FALLBACK", "HTML_PRE", "HTML_P", "HTML_LI", "HTML_SINGLE_CELL_ROW"}


@dataclass(frozen=True)
class RangeBinding:
    metric: str
    fiscal_period: str
    accounting_basis: str
    metric_subtype: str
    unit: str
    lower_bound: float
    upper_bound: float
    midpoint: float
    numeric_role: str
    sign: str
    source_structure: str
    range_offset: int
    range_role: str = "CURRENT_CANDIDATE"
    semantic_role: str = "CURRENT_GUIDANCE_RANGE"
    table_index: int | None = None
    row_index: int | None = None
    column_index: int | None = None
    row_header: str = ""
    header_path: str = ""
    source_excerpt: str = ""
    candidate_status: str = "V4_ATOMIC_BINDING_NOT_SOURCE_REVIEWED"


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _basis(metric_text: str, metric: str) -> str:
    if re.search(r"\b(?:non[- ]GAAP|adjusted|normalized|core|before charges)\b", metric_text, re.I):
        return "NON_GAAP"
    if re.search(r"\b(?:GAAP|reported basis)\b", metric_text, re.I):
        return "GAAP"
    if metric in {"CAPEX", "CASH_CAPEX"}:
        return "NOT_APPLICABLE"
    return "UNSPECIFIED"


def _explicit_metric(value: str, ticker: str, aliases: list[Alias]) -> tuple[str, Alias, int, int] | None:
    matches = []
    for alias in aliases:
        if alias.ticker_scope is not None and ticker not in alias.ticker_scope:
            continue
        for match in alias.pattern.finditer(value):
            matches.append((match.start(), match.end(), alias))
    if not matches:
        return None
    matches.sort(key=lambda item: (item[0], item[1] - item[0]))
    start, end, alias = matches[-1]
    overlapping = {item[2].canonical_metric for item in matches if item[0] == start and item[1] == end}
    if len(overlapping) != 1:
        return None
    return alias.canonical_metric, alias, start, end


def _periods(value: str) -> list[str]:
    found = []
    patterns = [
        (re.compile(r"\b(?:FY|fiscal\s+year|full[- ]year)\s*(20\d{2})\b", re.I), lambda m: f"FY{m.group(1)}"),
        (re.compile(r"\b(?:first|1st)\s+quarter(?:\s+of)?(?:\s+fiscal(?:\s+year)?)?\s+(20\d{2})\b", re.I), lambda m: f"Q1-{m.group(1)}"),
        (re.compile(r"\b(?:second|2nd)\s+quarter(?:\s+of)?(?:\s+fiscal(?:\s+year)?)?\s+(20\d{2})\b", re.I), lambda m: f"Q2-{m.group(1)}"),
        (re.compile(r"\b(?:third|3rd)\s+quarter(?:\s+of)?(?:\s+fiscal(?:\s+year)?)?\s+(20\d{2})\b", re.I), lambda m: f"Q3-{m.group(1)}"),
        (re.compile(r"\b(?:fourth|4th)\s+quarter(?:\s+of)?(?:\s+fiscal(?:\s+year)?)?\s+(20\d{2})\b", re.I), lambda m: f"Q4-{m.group(1)}"),
        (re.compile(r"\bQ([1-4])\s*(?:of\s+)?(?:FY)?\s*(20\d{2})\b", re.I), lambda m: f"Q{m.group(1)}-{m.group(2)}"),
    ]
    for pattern, formatter in patterns:
        found.extend(formatter(match) for match in pattern.finditer(value))
    return list(dict.fromkeys(found))


def _normalize_candidate(candidate: dict, *, sign: str) -> tuple[float, float] | None:
    low, high = float(candidate["lower_bound"]), float(candidate["upper_bound"])
    if sign == "NEGATIVE":
        low, high = -abs(high), -abs(low)
    return (low, high) if _plausible_bounds(low, high) else None


def _narrative_binding(text: str, ticker: str, aliases: list[Alias]) -> list[dict]:
    output = []
    candidates = parse_block_v2(text, ticker, aliases)
    ranges = list(RANGE.finditer(text))
    for candidate in candidates:
        offset = int(candidate["range_offset"])
        match = next((item for item in ranges if item.start() == offset), None)
        if match is None or candidate["semantic_role"] != "CURRENT_GUIDANCE_RANGE":
            continue
        sentence_start, sentence_end = _sentence_bounds(text, offset)
        clause = text[sentence_start:sentence_end]
        local_offset = offset - sentence_start
        before = clause[:local_offset]
        after = clause[local_offset + len(match.group(0)):]
        metric_match = _explicit_metric(before, ticker, aliases)
        if metric_match is None:
            continue
        metric, alias, metric_start, _ = metric_match
        if metric != candidate["metric"] or not FORWARD_CONTEXT.search(clause):
            continue
        if HISTORICAL_RECAP.search(clause) and not CURRENT_HEADER.search(clause):
            continue
        if re.match(r"^\s*to\s+(?:a\s+)?(?:new\s+)?range", after, re.I):
            continue
        if re.search(r"\brespectively\b", after, re.I) and re.search(r"\band\b", match.group(0), re.I):
            continue
        period = _range_local_period(clause, local_offset)
        all_periods = _periods(clause)
        if period is None or period not in all_periods:
            continue
        # 보고 분기와 전망 기간이 같이 있으면 명시적인 forward 문맥 이후 기간만 허용한다.
        forward = list(FORWARD_CONTEXT.finditer(before))
        if not forward:
            continue
        forward_tail = before[forward[-1].end():]
        forward_periods = _periods(forward_tail)
        if REPORTING_CONTEXT.search(before[:forward[-1].start()]) and period not in forward_periods:
            continue
        nearest = _nearest_metric(clause, local_offset)
        if nearest is None or nearest[0] != metric:
            continue
        if not _semantic_context_is_current(clause, local_offset):
            continue
        sign = "NEGATIVE" if USE_OF_CASH.search(before[metric_start:]) else "AS_REPORTED"
        bounds = _normalize_candidate(candidate, sign=sign)
        if bounds is None:
            continue
        low, high = bounds
        basis = _basis(before[metric_start:], metric)
        output.append(asdict(RangeBinding(
            metric=metric,
            fiscal_period=period,
            accounting_basis=basis if basis != "UNSPECIFIED" else _range_local_basis(clause, metric_start, local_offset, metric),
            metric_subtype=_metric_subtype(clause, metric_start, metric, candidate["metric_subtype"]),
            unit=candidate["unit"],
            lower_bound=low,
            upper_bound=high,
            midpoint=(low + high) / 2,
            numeric_role="CURRENT_GUIDANCE_RANGE",
            sign=sign,
            source_structure="NARRATIVE_CLAUSE",
            range_offset=offset,
            source_excerpt=_clean(clause)[:1000],
        )))
    return output


def _table_title(table: etree._Element) -> str:
    pieces = []
    for sibling in table.itersiblings(preceding=True):
        if not isinstance(sibling.tag, str):
            continue
        value = _clean(sibling.text_content())
        if value:
            pieces.append(value)
        if len(pieces) == 3:
            break
    return " | ".join(reversed(pieces))[-1200:]


def _header_path(grid: list[list[str]], row: int, column: int) -> str:
    values = []
    for prior in range(row):
        if column < len(grid[prior]) and grid[prior][column]:
            value = _clean(grid[prior][column])
            if value and value not in values:
                values.append(value)
    return " | ".join(values)


def _current_columns(row: list[str], grid: list[list[str]], row_index: int, value_columns: list[int]) -> set[int]:
    headers = {column: _header_path(grid, row_index, column) for column in value_columns}
    explicit = {column for column, value in headers.items() if CURRENT_HEADER.search(value) and not PRIOR_HEADER.search(value)}
    if explicit:
        return explicit
    dated = []
    for column, value in headers.items():
        matches = list(AS_OF_DATE.finditer(value))
        if matches:
            match = matches[-1]
            month = MONTHS[match.group(0).lstrip().split()[2 if match.group(0).lower().startswith("as of") else 0][:3].lower()]
            dated.append((datetime(int(match.group(2)), month, int(match.group(1))), column))
    if len(dated) >= 2:
        latest = max(item[0] for item in dated)
        return {column for key, column in dated if key == latest}
    return set(value_columns) if len(value_columns) == 1 else set()


def _table_bindings(content: bytes, ticker: str, aliases: list[Alias]) -> list[dict]:
    try:
        document = html.fromstring(content)
    except (ValueError, etree.ParserError):
        return []
    output = []
    for table_index, table in enumerate(document.xpath("//table")):
        grid = expand_table(table)
        title = _table_title(table)
        table_text = _clean(table.text_content())
        if not (GUIDANCE.search(title) or GUIDANCE.search(table_text)):
            continue
        for row_index, row in enumerate(grid):
            value_columns = [column for column, value in enumerate(row) if RANGE.search(value)]
            if not value_columns:
                continue
            current = _current_columns(row, grid, row_index, value_columns)
            for column in value_columns:
                if column not in current:
                    continue
                # 현재 열 왼쪽의 과거 수치 셀은 행 머리글이 아니다.
                label_end = min(value_columns)
                row_header = " | ".join(_clean(value) for value in row[:label_end] if _clean(value))
                metric_match = _explicit_metric(row_header, ticker, aliases)
                if metric_match is None:
                    continue
                metric, alias, metric_start, _ = metric_match
                header_path = _header_path(grid, row_index, column)
                period_candidates = _periods(f"{header_path} | {row_header} | {title}")
                if len(period_candidates) != 1:
                    continue
                basis = _basis(row_header, metric)
                for match in RANGE.finditer(row[column]):
                    # V2 정규화기를 같은 셀·같은 행 지표에만 사용한다.
                    synthetic = f"guidance for {period_candidates[0].replace('FY', 'fiscal year ')} {row_header} {match.group(0)}"
                    parsed = parse_block_v2(synthetic, ticker, [alias])
                    if len(parsed) != 1:
                        continue
                    candidate = parsed[0]
                    sign = "NEGATIVE" if USE_OF_CASH.search(row_header) else "AS_REPORTED"
                    bounds = _normalize_candidate(candidate, sign=sign)
                    if bounds is None:
                        continue
                    low, high = bounds
                    output.append(asdict(RangeBinding(
                        metric=metric,
                        fiscal_period=period_candidates[0],
                        accounting_basis=basis if basis != "UNSPECIFIED" else alias.accounting_basis,
                        metric_subtype="NOT_APPLICABLE",
                        unit=candidate["unit"],
                        lower_bound=low,
                        upper_bound=high,
                        midpoint=(low + high) / 2,
                        numeric_role="CURRENT_GUIDANCE_RANGE",
                        sign=sign,
                        source_structure="HTML_TABLE_GRID",
                        range_offset=match.start(),
                        table_index=table_index,
                        row_index=row_index,
                        column_index=column,
                        row_header=row_header[:500],
                        header_path=header_path[:500],
                        source_excerpt=_clean(f"{title} | {' | '.join(row)}")[:1200],
                    )))
    return output


def parse_document_v4(content: bytes, ticker: str, aliases: list[Alias]) -> list[dict]:
    decoded = content.decode("utf-8", errors="replace")
    if not GUIDANCE.search(decoded) or not RANGE.search(decoded):
        return []
    output = _table_bindings(content, ticker, aliases)
    for block in structured_blocks(content):
        if block["source_kind"] not in NARRATIVE_SOURCE_KINDS:
            continue
        for binding in _narrative_binding(block["block_text"], ticker, aliases):
            output.append({**binding, "block_path": block["block_path"], "source_kind": block["source_kind"]})
    unique = {}
    for item in output:
        key = (
            item["metric"], item["fiscal_period"], item["accounting_basis"], item["metric_subtype"],
            item["unit"], item["lower_bound"], item["upper_bound"], item["source_structure"],
            item.get("table_index"), item.get("row_index"), item.get("column_index"), item.get("block_path"),
        )
        unique.setdefault(key, item)
    return list(unique.values())


def build(
    corpora: list[Path],
    aliases: list[Alias],
    protocol: dict,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    excluded = set()
    for path in protocol["development_reviews"]:
        excluded.update(pd.read_csv(path)["accession_number"].astype(str))
    records = []
    for corpus in corpora:
        index = pd.read_csv(corpus / "index.csv", dtype={"cik": str})
        for _, source in index.iterrows():
            content = gzip.open(corpus / source["path"], "rb").read()
            for candidate in parse_document_v4(content, source["ticker"], aliases):
                records.append({
                    "ticker": source["ticker"], "cik": source["cik"],
                    "accession_number": source["accession_number"], "accepted_at": source["accepted_at"],
                    "document_name": source["document_name"], "source_url": source["source_url"],
                    "source_sha256": source["source_sha256"], **candidate,
                })
    candidates = pd.DataFrame(records)
    if not candidates.empty:
        candidates["review_priority"] = candidates.apply(lambda row: hashlib.sha256(
            f'{row["source_sha256"]}:{row["source_structure"]}:{row["range_offset"]}:{row["metric"]}'.encode()
        ).hexdigest(), axis=1)
        candidates = candidates.drop_duplicates([
            "ticker", "accession_number", "metric", "fiscal_period", "accounting_basis", "metric_subtype",
            "unit", "lower_bound", "upper_bound", "source_structure", "range_offset",
        ])
    holdout = candidates.loc[~candidates["accession_number"].astype(str).isin(excluded)].copy() if not candidates.empty else candidates.copy()
    review = select_stratified_review(holdout, protocol["review_gate"]["target_rows_per_metric"])
    minimum = protocol["review_gate"]["minimum_stratified_rows"]
    if len(review) < minimum and not holdout.empty:
        selected = set(review.index)
        groups = [group for _, group in holdout.sort_values("review_priority").groupby("metric", sort=True)]
        cursors = [0] * len(groups)
        while len(selected) < min(minimum, len(holdout)):
            added = False
            for group_index, group in enumerate(groups):
                while cursors[group_index] < len(group):
                    index = group.index[cursors[group_index]]
                    cursors[group_index] += 1
                    if index not in selected:
                        selected.add(index)
                        added = True
                        break
                if len(selected) >= min(minimum, len(holdout)):
                    break
            if not added:
                break
        review = holdout.loc[sorted(selected)].sort_values(["metric", "review_priority"]).copy()
    if not review.empty:
        review.insert(0, "review_id", [f"SG4-{i:04d}" for i in range(1, len(review) + 1)])
        for column, default in [("review_decision", "PENDING"), ("review_reason", ""), ("reviewer", ""), ("reviewed_at", "")]:
            review[column] = default
    gate = protocol["review_gate"]
    ready = len(review) >= gate["minimum_stratified_rows"] and review["ticker"].nunique() >= gate["minimum_distinct_tickers"] if not review.empty else False
    return candidates, review, {
        "report_version": "herd-sec-guidance-structure-parser-v4",
        "input_corpora": [str(path) for path in corpora],
        "development_accessions_excluded": len(excluded),
        "v4_candidates": len(candidates),
        "v4_candidate_tickers": int(candidates["ticker"].nunique()) if not candidates.empty else 0,
        "fresh_holdout_candidates": len(holdout),
        "fresh_holdout_tickers": int(holdout["ticker"].nunique()) if not holdout.empty else 0,
        "fresh_review_rows": len(review),
        "fresh_review_tickers": int(review["ticker"].nunique()) if not review.empty else 0,
        "review_sample_gate_ready": ready,
        "review_gate_passed": False,
        "source_qualified_revision_pairs": 0,
        "ready_for_direction_preregistration": False,
        "next_decision": "COMPLETE_FRESH_V4_SOURCE_REVIEW" if ready else "FRESH_V4_REVIEW_SAMPLE_COVERAGE_BLOCKED",
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
    candidates, review, report = build(
        [Path(path) for path in protocol["input_corpora"]],
        load_aliases(Path(protocol["alias_registry"])),
        protocol,
    )
    candidates.to_csv(args.candidates, index=False, float_format="%.12g", lineterminator="\n")
    review.to_csv(args.review, index=False, float_format="%.12g", lineterminator="\n")
    report["protocol_sha256"] = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
