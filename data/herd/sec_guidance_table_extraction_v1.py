"""EDGAR HTML 표의 셀 구조를 보존해 명시적 가이던스 범위 후보를 만든다."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from pathlib import Path

import pandas as pd
from lxml import etree, html

from herd.sec_8k_guidance_coverage_v1 import GUIDANCE
from herd.sec_guidance_normalization_v1 import (
    METRICS,
    PERIOD_PATTERNS,
    RANGE,
    _basis,
    _normalize_range,
)


PROTOCOL = Path(__file__).with_suffix(".json")


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def expand_table(table: etree._Element) -> list[list[str]]:
    """rowspan/colspan을 실제 격자로 펼친다."""
    grid: list[list[str]] = []
    spans: dict[tuple[int, int], str] = {}
    for row_index, tr in enumerate(table.xpath(".//tr")):
        row: list[str] = []
        column = 0
        cells = tr.xpath("./th|./td")
        while (row_index, column) in spans:
            row.append(spans[(row_index, column)])
            column += 1
        for cell in cells:
            while (row_index, column) in spans:
                row.append(spans[(row_index, column)])
                column += 1
            value = _clean(cell.text_content())
            rowspan = max(1, int(cell.get("rowspan", "1") or 1))
            colspan = max(1, int(cell.get("colspan", "1") or 1))
            for offset in range(colspan):
                row.append(value)
                for future_row in range(row_index + 1, row_index + rowspan):
                    spans[(future_row, column + offset)] = value
            column += colspan
        while (row_index, column) in spans:
            row.append(spans[(row_index, column)])
            column += 1
        grid.append(row)
    width = max((len(row) for row in grid), default=0)
    return [row + [""] * (width - len(row)) for row in grid]


def _period(value: str) -> str | None:
    candidates = []
    for pattern, formatter in PERIOD_PATTERNS:
        candidates.extend(formatter(match) for match in pattern.finditer(value))
    return candidates[0] if len(set(candidates)) == 1 else None


def _nearest_preceding_metric(value: str) -> str | None:
    matches = []
    for metric, pattern in METRICS.items():
        matches.extend((match.end(), metric) for match in pattern.finditer(value))
    if not matches:
        return None
    matches.sort()
    nearest_end = matches[-1][0]
    nearest = {metric for end, metric in matches if end == nearest_end}
    return next(iter(nearest)) if len(nearest) == 1 else None


def extract_table_candidates(content: bytes) -> list[dict]:
    try:
        document = html.fromstring(content)
    except (ValueError, etree.ParserError):
        return []
    output = []
    for table_index, table in enumerate(document.xpath("//table")):
        grid = expand_table(table)
        table_text = _clean(table.text_content())
        if not GUIDANCE.search(table_text):
            continue
        for row_index, row in enumerate(grid):
            row_text = " | ".join(cell for cell in row if cell)
            if not RANGE.search(row_text):
                continue
            for column_index, cell in enumerate(row):
                range_matches = list(RANGE.finditer(cell))
                if not range_matches:
                    continue
                header_context = " | ".join(
                    grid[prior][column_index]
                    for prior in range(max(0, row_index - 6), row_index)
                    if column_index < len(grid[prior]) and grid[prior][column_index]
                )
                for range_match in range_matches:
                    preceding = " | ".join(x for x in row[:column_index] if x)
                    preceding = f"{preceding} | {cell[:range_match.start()]}"
                    metric = _nearest_preceding_metric(preceding)
                    if metric is None:
                        continue
                    period = _period(preceding) or _period(header_context)
                    if period is None:
                        continue
                    local_range = range_match.group(0) + cell[range_match.end(): min(len(cell), range_match.end() + 30)]
                    if metric == "EPS" and not re.search(r"[$€£]|\bcents?\b|\bper share\b", local_range, re.I):
                        continue
                    context = f"{header_context} | {row_text}"
                    normalized = _normalize_range(range_match, metric, context)
                    if normalized is None:
                        continue
                    low, high, unit = normalized
                    output.append({
                        "table_index": table_index,
                        "row_index": row_index,
                        "column_index": column_index,
                        "metric": metric,
                        "fiscal_period": period,
                        "accounting_basis": _basis(context),
                        "unit": unit,
                        "lower_bound": low,
                        "upper_bound": high,
                        "midpoint": (low + high) / 2,
                        "header_context": header_context[:500],
                        "source_row": row_text[:1000],
                        "candidate_status": "STRUCTURE_PRESERVED_NOT_SOURCE_REVIEWED",
                    })
    unique = {}
    for row in output:
        key = (
            row["table_index"], row["row_index"], row["column_index"], row["metric"],
            row["fiscal_period"], row["accounting_basis"], row["unit"],
            row["lower_bound"], row["upper_bound"],
        )
        unique.setdefault(key, row)
    return list(unique.values())


def build(corpus: Path, protocol: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    index = pd.read_csv(corpus / "index.csv", dtype={"cik": str})
    records = []
    html_documents = 0
    for _, source in index.iterrows():
        content = gzip.open(corpus / source["path"], "rb").read()
        if b"<table" not in content.lower():
            continue
        html_documents += 1
        for candidate in extract_table_candidates(content):
            records.append({
                "ticker": source["ticker"], "cik": source["cik"],
                "accession_number": source["accession_number"],
                "accepted_at": source["accepted_at"],
                "document_name": source["document_name"],
                "document_role": source["document_role"],
                "source_url": source["source_url"],
                "source_sha256": source["source_sha256"],
                **candidate,
            })
    candidates = pd.DataFrame(records)
    if not candidates.empty:
        candidates = candidates.sort_values(
            ["metric", "ticker", "accepted_at", "accession_number", "table_index", "row_index", "column_index"]
        ).drop_duplicates(
            ["ticker", "accession_number", "metric", "fiscal_period", "accounting_basis", "unit", "lower_bound", "upper_bound"]
        )
    target = protocol["review_gate"]["target_rows_per_metric"]
    if not candidates.empty:
        candidates["review_priority"] = candidates.apply(
            lambda row: hashlib.sha256(
                f'{row["source_sha256"]}:{row["table_index"]}:{row["row_index"]}:{row["column_index"]}:{row["metric"]}'.encode()
            ).hexdigest(),
            axis=1,
        )
    review = (
        candidates.sort_values(["metric", "review_priority"]).groupby("metric", group_keys=False).head(target).copy()
        if not candidates.empty else candidates.copy()
    )
    if not review.empty:
        review.insert(0, "review_id", [f"SGT-{i:04d}" for i in range(1, len(review) + 1)])
        review["review_decision"] = "PENDING"
        review["review_reason"] = ""
        review["reviewer"] = ""
        review["reviewed_at"] = ""
    metric_counts = candidates.groupby("metric").size().to_dict() if not candidates.empty else {}
    report = {
        "report_version": "herd-sec-guidance-table-extraction-v1",
        "snapshot_id": json.loads((corpus / "manifest.json").read_text())["snapshot_id"],
        "html_documents_scanned": html_documents,
        "structure_preserved_candidates": len(candidates),
        "candidate_tickers": int(candidates["ticker"].nunique()) if not candidates.empty else 0,
        "candidate_counts_by_metric": {key: int(value) for key, value in metric_counts.items()},
        "stratified_review_rows": len(review),
        "reviewed_rows": 0,
        "source_precision": None,
        "wilson_95_lower_bound": None,
        "review_gate_passed": False,
        "source_verified_pairs": 0,
        "source_verified_tickers": 0,
        "coverage_gate_passed": False,
        "ready_for_direction_preregistration": False,
        "next_decision": (
            "COMPLETE_STRATIFIED_SOURCE_REVIEW"
            if len(review) >= protocol["review_gate"]["minimum_stratified_rows"]
            else "REVIEW_SAMPLE_COVERAGE_BLOCKED"
        ),
        "guidance_direction_classified": 0,
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
    candidates, review, report = build(Path(protocol["corpus"]), protocol)
    args.candidates.parent.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(args.candidates, index=False, float_format="%.12g", lineterminator="\n")
    review.to_csv(args.review, index=False, float_format="%.12g", lineterminator="\n")
    report["protocol_sha256"] = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
