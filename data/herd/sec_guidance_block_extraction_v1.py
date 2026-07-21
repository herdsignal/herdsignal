"""EDGAR 문서의 줄·블록 경계를 보존해 issuer-scoped 가이던스 후보를 만든다."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from lxml import etree, html

from herd.sec_8k_guidance_coverage_v1 import GUIDANCE
from herd.sec_guidance_normalization_v1 import PERIOD_PATTERNS, RANGE, SCALE_FACTOR, _number


PROTOCOL = Path(__file__).with_suffix(".json")
BLOCK_TAGS = {"p", "li", "pre", "div"}


@dataclass(frozen=True)
class Alias:
    canonical_metric: str
    pattern: re.Pattern
    accounting_basis: str
    unit_family: str
    ticker_scope: frozenset[str] | None
    alias_pattern: str


def _clean(value: str) -> str:
    return re.sub(r"[ \t\f\v]+", " ", value).strip()


def load_aliases(path: Path) -> list[Alias]:
    rows = pd.read_csv(path).fillna("")
    aliases = []
    for row in rows.itertuples(index=False):
        scope = None if row.ticker_scope == "*" else frozenset(x.strip() for x in row.ticker_scope.split(","))
        aliases.append(Alias(
            row.canonical_metric,
            re.compile(rf"\b(?:{row.alias_pattern})\b", re.I),
            row.accounting_basis,
            row.unit_family,
            scope,
            row.alias_pattern,
        ))
    return aliases


def _ascii_blocks(text: str, source_kind: str) -> list[dict]:
    blocks, current = [], []
    for line_number, raw in enumerate(text.replace("\r\n", "\n").replace("\r", "\n").split("\n"), start=1):
        line = _clean(raw)
        if line:
            current.append((line_number, line))
        elif current:
            blocks.append({
                "source_kind": source_kind,
                "block_path": f"lines:{current[0][0]}-{current[-1][0]}",
                "block_text": "\n".join(value for _, value in current),
            })
            current = []
    if current:
        blocks.append({
            "source_kind": source_kind,
            "block_path": f"lines:{current[0][0]}-{current[-1][0]}",
            "block_text": "\n".join(value for _, value in current),
        })
    return blocks


def structured_blocks(content: bytes) -> list[dict]:
    decoded = content.decode("utf-8", errors="replace")
    if not re.search(r"<\s*(?:html|body|div|p|table|pre|li)\b", decoded, re.I):
        return _ascii_blocks(decoded, "ASCII")
    try:
        document = html.fromstring(content)
    except (ValueError, etree.ParserError):
        return _ascii_blocks(decoded, "ASCII_PARSE_FALLBACK")
    blocks = []
    tree = document.getroottree()
    for element in document.xpath("//pre"):
        blocks.extend({**block, "block_path": f"{tree.getpath(element)}:{block['block_path']}"}
                      for block in _ascii_blocks(element.text_content(), "HTML_PRE"))
    for element in document.xpath("//p|//li|//div"):
        tag = element.tag.lower() if isinstance(element.tag, str) else ""
        if tag not in BLOCK_TAGS or element.xpath(".//p|.//li|.//div|.//pre"):
            continue
        if element.xpath("ancestor::pre"):
            continue
        value = _clean(element.text_content())
        if value:
            blocks.append({"source_kind": f"HTML_{tag.upper()}", "block_path": tree.getpath(element), "block_text": value})
    # EDGAR의 1셀 레이아웃 표는 문단 역할을 하므로 행 경계를 유지해 별도 블록으로 취급한다.
    for row in document.xpath("//tr"):
        cells = row.xpath("./th|./td")
        if len(cells) != 1 or row.xpath("ancestor::pre"):
            continue
        value = _clean(cells[0].text_content())
        if value:
            blocks.append({"source_kind": "HTML_SINGLE_CELL_ROW", "block_path": tree.getpath(row), "block_text": value})
    unique = {}
    for block in blocks:
        unique.setdefault((block["source_kind"], block["block_path"], block["block_text"]), block)
    return list(unique.values())


def _period_before(value: str) -> tuple[str, int] | None:
    matches = []
    for pattern, formatter in PERIOD_PATTERNS:
        matches.extend((match.end(), formatter(match)) for match in pattern.finditer(value))
    if not matches:
        return None
    matches.sort()
    nearest_end = matches[-1][0]
    periods = {period for end, period in matches if end == nearest_end}
    return (next(iter(periods)), len(value) - nearest_end) if len(periods) == 1 else None


def _nearest_alias(value: str, ticker: str, aliases: list[Alias]) -> tuple[Alias, int] | None:
    matches = []
    for alias in aliases:
        if alias.ticker_scope is not None and ticker not in alias.ticker_scope:
            continue
        matches.extend((match.end(), match.end() - match.start(), alias) for match in alias.pattern.finditer(value))
    if not matches:
        return None
    matches.sort(key=lambda item: (item[0], item[1]))
    nearest_end = matches[-1][0]
    longest = max(item[1] for item in matches if item[0] == nearest_end)
    nearest = {item[2] for item in matches if item[0] == nearest_end and item[1] == longest}
    return (next(iter(nearest)), len(value) - nearest_end) if len(nearest) == 1 else None


def _normalize(match: re.Match, alias: Alias, suffix: str) -> tuple[float, float, str] | None:
    low, high = _number(match.group("low")), _number(match.group("high"))
    low_scale = (match.group("low_scale") or "").lower()
    high_scale = (match.group("high_scale") or "").lower()
    scale = high_scale or low_scale
    local = match.group(0) + suffix[:35]
    if alias.unit_family == "PERCENT":
        if scale not in {"%", "percent", "percentage point", "percentage points"} and "%" not in local:
            return None
        unit, factor = "PERCENT", 1.0
    elif alias.unit_family in {"USD_PER_SHARE", "USD_OR_PER_SHARE"} and re.search(r"[$€£]|\bcents?\b|\bper share\b", local, re.I):
        unit, factor = "USD_PER_SHARE", 0.01 if scale == "cents" else 1.0
    else:
        if scale not in SCALE_FACTOR:
            return None
        unit, factor = "USD", SCALE_FACTOR[scale]
    low, high = low * factor, high * factor
    return (min(low, high), max(low, high), unit)


def extract_block_candidates(
    block_text: str, ticker: str, aliases: list[Alias], limits: dict | None = None,
) -> list[dict]:
    limits = limits or {
        "maximum_alias_distance_chars": 140,
        "maximum_period_distance_chars": 320,
        "maximum_guidance_distance_chars": 260,
    }
    if not GUIDANCE.search(block_text):
        return []
    output = []
    for match in RANGE.finditer(block_text):
        preceding = block_text[:match.start()]
        alias_match = _nearest_alias(preceding, ticker, aliases)
        period_match = _period_before(preceding)
        guidance_matches = list(GUIDANCE.finditer(preceding))
        guidance_distance = len(preceding) - guidance_matches[-1].end() if guidance_matches else None
        if alias_match is None or period_match is None or guidance_distance is None:
            continue
        alias, alias_distance = alias_match
        period, period_distance = period_match
        if (
            alias_distance > limits["maximum_alias_distance_chars"]
            or period_distance > limits["maximum_period_distance_chars"]
            or guidance_distance > limits["maximum_guidance_distance_chars"]
        ):
            continue
        local_prefix = preceding[-100:]
        if re.search(r"\bmidpoints?\b.{0,60}\bby\b", local_prefix, re.I):
            continue
        normalized = _normalize(match, alias, block_text[match.end():])
        if normalized is None:
            continue
        low, high, unit = normalized
        prior_reference = bool(re.search(r"\b(?:prior|previous(?:ly)?)\b[^.;:]{0,90}$", local_prefix, re.I))
        basis = alias.accounting_basis
        output.append({
            "metric": alias.canonical_metric,
            "matched_alias": alias.alias_pattern,
            "fiscal_period": period,
            "accounting_basis": basis,
            "unit": unit,
            "lower_bound": low,
            "upper_bound": high,
            "midpoint": (low + high) / 2,
            "range_offset": match.start(),
            "range_role": "PRIOR_REFERENCE" if prior_reference else "CURRENT_CANDIDATE",
            "candidate_status": "BLOCK_PRESERVED_NOT_SOURCE_REVIEWED",
        })
    return output


def select_stratified_review(candidates: pd.DataFrame, target_per_metric: int) -> pd.DataFrame:
    if candidates.empty:
        return candidates.copy()
    pool = candidates.loc[candidates["range_role"].eq("CURRENT_CANDIDATE")].sort_values("review_priority")
    issuer_seed = pool.groupby("ticker", group_keys=False).head(1)
    selected = {index for index in issuer_seed.index}
    for _, group in pool.groupby("metric", sort=True):
        existing = sum(index in selected for index in group.index)
        needed = max(0, target_per_metric - existing)
        for index in group.index:
            if needed == 0:
                break
            if index not in selected:
                selected.add(index)
                needed -= 1
    return pool.loc[sorted(selected)].sort_values(["metric", "review_priority"]).copy()


def build(corpus: Path, aliases: list[Alias], protocol: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    index = pd.read_csv(corpus / "index.csv", dtype={"cik": str})
    records, kinds = [], {}
    for _, source in index.iterrows():
        content = gzip.open(corpus / source["path"], "rb").read()
        for block in structured_blocks(content):
            kinds[block["source_kind"]] = kinds.get(block["source_kind"], 0) + 1
            for candidate in extract_block_candidates(
                block["block_text"], source["ticker"], aliases, protocol["association_limits"],
            ):
                records.append({
                    "ticker": source["ticker"], "cik": source["cik"],
                    "accession_number": source["accession_number"], "accepted_at": source["accepted_at"],
                    "document_name": source["document_name"], "document_role": source["document_role"],
                    "source_url": source["source_url"], "source_sha256": source["source_sha256"],
                    **block, **candidate,
                })
    candidates = pd.DataFrame(records)
    if not candidates.empty:
        candidates["review_priority"] = candidates.apply(
            lambda row: hashlib.sha256(
                f'{row["source_sha256"]}:{row["block_path"]}:{row["range_offset"]}:{row["metric"]}'.encode()
            ).hexdigest(), axis=1,
        )
        candidates = candidates.sort_values(["metric", "review_priority"]).drop_duplicates(
            ["ticker", "accession_number", "block_path", "metric", "fiscal_period", "unit", "lower_bound", "upper_bound"]
        )
    target = protocol["review_gate"]["target_rows_per_metric"]
    review = select_stratified_review(candidates, target)
    if not review.empty:
        review.insert(0, "review_id", [f"SGB-{i:04d}" for i in range(1, len(review) + 1)])
        for column, default in [("review_decision", "PENDING"), ("review_reason", ""), ("reviewer", ""), ("reviewed_at", "")]:
            review[column] = default
    gate = protocol["review_gate"]
    sample_ready = len(review) >= gate["minimum_stratified_rows"] and review["ticker"].nunique() >= gate["minimum_distinct_tickers"] if not review.empty else False
    counts = candidates.groupby("metric").size().to_dict() if not candidates.empty else {}
    report = {
        "report_version": "herd-sec-guidance-block-extraction-v1",
        "snapshot_id": json.loads((corpus / "manifest.json").read_text())["snapshot_id"],
        "source_blocks_by_kind": kinds,
        "block_preserved_candidates": len(candidates),
        "candidate_tickers": int(candidates["ticker"].nunique()) if not candidates.empty else 0,
        "candidate_counts_by_metric": {key: int(value) for key, value in counts.items()},
        "stratified_review_rows": len(review),
        "stratified_review_tickers": int(review["ticker"].nunique()) if not review.empty else 0,
        "review_sample_gate_ready": sample_ready,
        "review_gate_passed": False,
        "source_qualified_revision_pairs": 0,
        "coverage_gate_passed": False,
        "ready_for_direction_preregistration": False,
        "next_decision": "COMPLETE_STRATIFIED_SOURCE_REVIEW" if sample_ready else "REVIEW_SAMPLE_COVERAGE_BLOCKED",
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
    aliases = load_aliases(Path(protocol["alias_registry"]))
    candidates, review, report = build(Path(protocol["corpus"]), aliases, protocol)
    args.candidates.parent.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(args.candidates, index=False, float_format="%.12g", lineterminator="\n")
    review.to_csv(args.review, index=False, float_format="%.12g", lineterminator="\n")
    report["protocol_sha256"] = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    report["alias_registry_sha256"] = hashlib.sha256(Path(protocol["alias_registry"]).read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
