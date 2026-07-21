"""SEC 8-K에서 명시적인 동질 가이던스 범위와 연속 revision pair만 만든다."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from pathlib import Path

import pandas as pd

from herd.sec_8k_guidance_coverage_v1 import GUIDANCE, plain_text


PROTOCOL = Path(__file__).with_suffix(".json")
QUARTERS = {"first": "1", "second": "2", "third": "3", "fourth": "4"}
METRICS = {
    "REVENUE": re.compile(r"\b(revenue|net sales)\b", re.I),
    "EPS": re.compile(r"\b(earnings per share|diluted EPS|adjusted EPS|EPS)\b", re.I),
    "MARGIN": re.compile(r"\b(operating margin|gross margin|EBITDA margin)\b", re.I),
    "OPERATING_INCOME": re.compile(r"\b(operating income|adjusted EBITDA|EBITDA)\b", re.I),
    "FREE_CASH_FLOW": re.compile(r"\b(free cash flow|operating cash flow)\b", re.I),
    "CAPEX": re.compile(r"\b(capital expenditures|capital spending|capex)\b", re.I),
}
PERIOD_PATTERNS = [
    (re.compile(r"\b(?:FY|fiscal\s+year|full[- ]year)\s*(20\d{2})\b", re.I), lambda m: f"FY{m.group(1)}"),
    (re.compile(r"\b(20\d{2})\s+(?:fiscal|full)[- ]year\b", re.I), lambda m: f"FY{m.group(1)}"),
    (re.compile(r"\bQ([1-4])\s*[- ]?\s*(20\d{2})\b", re.I), lambda m: f"Q{m.group(1)}-{m.group(2)}"),
    (re.compile(r"\b(first|second|third|fourth)\s+quarter(?:\s+of)?\s+(20\d{2})\b", re.I),
     lambda m: f"Q{QUARTERS[m.group(1).lower()]}-{m.group(2)}"),
]
NUMBER = r"(?P<{name}>\(?-?[$€£]?\s*\d{{1,3}}(?:,\d{{3}})*(?:\.\d+)?\)?)"
SCALE = r"(?P<{name}>billion|million|thousand|%|percent|percentage points?|cents|per share)?"
RANGE = re.compile(
    NUMBER.format(name="low") + r"\s*" + SCALE.format(name="low_scale")
    + r"\s*(?:to|through|and|[-–—])\s*"
    + NUMBER.format(name="high") + r"\s*" + SCALE.format(name="high_scale"), re.I,
)
SCALE_FACTOR = {"billion": 1e9, "million": 1e6, "thousand": 1e3}


def _number(value: str) -> float:
    cleaned = value.replace(",", "").replace("$", "").replace("€", "").replace("£", "").replace(" ", "")
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    result = float(cleaned)
    return -result if negative else result


def _nearest_period(text: str, center: int) -> str | None:
    start, end = max(0, center - 350), min(len(text), center + 350)
    candidates = []
    for pattern, formatter in PERIOD_PATTERNS:
        for match in pattern.finditer(text[start:end]):
            candidates.append((abs(start + (match.start() + match.end()) // 2 - center), formatter(match)))
    return min(candidates)[1] if candidates else None


def _basis(text: str) -> str:
    if re.search(r"\b(non[- ]GAAP|adjusted)\b", text, re.I):
        return "NON_GAAP"
    if re.search(r"\bGAAP\b", text, re.I):
        return "GAAP"
    return "UNSPECIFIED"


def _normalize_range(match: re.Match, metric: str, context: str) -> tuple[float, float, str] | None:
    low, high = _number(match.group("low")), _number(match.group("high"))
    low_scale = (match.group("low_scale") or "").lower()
    high_scale = (match.group("high_scale") or "").lower()
    shared_scale = high_scale or low_scale
    if metric == "EPS":
        if max(abs(low), abs(high)) > 100:
            return None
        if not re.search(r"[$€£]|\bcents?\b|\bper share\b", match.group(0) + " " + context, re.I):
            return None
        unit, factor = "USD_PER_SHARE", 0.01 if shared_scale == "cents" else 1.0
    elif metric == "MARGIN":
        if shared_scale not in {"%", "percent", "percentage point", "percentage points"} and "%" not in context:
            return None
        unit, factor = "PERCENT", 1.0
    else:
        if shared_scale not in SCALE_FACTOR:
            return None
        unit, factor = "USD", SCALE_FACTOR.get(shared_scale, 1.0)
    low, high = low * factor, high * factor
    if low > high:
        low, high = high, low
    return low, high, unit


def extract_ranges(text: str) -> list[dict]:
    rows = []
    guidance_spans = [(match.start(), match.end()) for match in GUIDANCE.finditer(text)]
    if not guidance_spans:
        return rows
    metric_spans = [
        (metric, match.start(), match.end())
        for metric, pattern in METRICS.items() for match in pattern.finditer(text)
    ]
    for range_match in RANGE.finditer(text):
        center = (range_match.start() + range_match.end()) // 2
        if min(abs((a + b) // 2 - center) for a, b in guidance_spans) > 500:
            continue
        candidates = sorted(
            (abs((start + end) // 2 - center), metric, start, end)
            for metric, start, end in metric_spans
            if abs((start + end) // 2 - center) <= 120
        )
        if not candidates:
            continue
        _, metric, metric_start, metric_end = candidates[0]
        window_start, window_end = max(0, min(metric_start, range_match.start()) - 220), min(len(text), max(metric_end, range_match.end()) + 220)
        window = text[window_start:window_end]
        normalized = _normalize_range(range_match, metric, window)
        period = _nearest_period(text, center)
        if normalized is None or period is None:
            continue
        low, high, unit = normalized
        rows.append({
            "metric": metric, "fiscal_period": period,
            "accounting_basis": _basis(window),
            "unit": unit, "lower_bound": low, "upper_bound": high,
            "midpoint": (low + high) / 2.0,
            "source_excerpt": re.sub(r"\s+", " ", window).strip()[:700],
        })
    unique = {}
    for row in rows:
        key = (row["metric"], row["fiscal_period"], row["accounting_basis"], row["unit"], row["lower_bound"], row["upper_bound"])
        unique.setdefault(key, row)
    return list(unique.values())


def normalize(corpus: Path, protocol: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    index = pd.read_csv(corpus / "index.csv", dtype={"cik": str})
    records = []
    for accession, documents in index.groupby("accession_number", sort=False):
        text = " ".join(
            plain_text(gzip.open(corpus / path, "rb").read())
            for path in documents["path"].drop_duplicates()
        )
        first = documents.iloc[0]
        for sequence, extracted in enumerate(extract_ranges(text), start=1):
            records.append({
                "ticker": first["ticker"], "cik": first["cik"],
                "accession_number": accession, "accepted_at": first["accepted_at"],
                "sequence": sequence, **extracted,
                "guidance_direction": "NOT_CLASSIFIED",
            })
    columns = [
        "ticker", "cik", "accession_number", "accepted_at", "sequence", "metric",
        "fiscal_period", "accounting_basis", "unit", "lower_bound", "upper_bound",
        "midpoint", "source_excerpt", "guidance_direction",
    ]
    guidance = pd.DataFrame(records, columns=columns)
    if not guidance.empty:
        guidance["accepted_at"] = pd.to_datetime(guidance["accepted_at"], utc=True)
        guidance = guidance.sort_values(["ticker", "metric", "fiscal_period", "accounting_basis", "unit", "accepted_at", "accession_number"])
    comparable = guidance.loc[guidance["accounting_basis"].ne("UNSPECIFIED")].copy()
    keys = protocol["required_pair_keys"]
    comparable["prior_accession_number"] = comparable.groupby(keys)["accession_number"].shift(1)
    comparable["prior_accepted_at"] = comparable.groupby(keys)["accepted_at"].shift(1)
    for field in ["lower_bound", "upper_bound", "midpoint"]:
        comparable[f"prior_{field}"] = comparable.groupby(keys)[field].shift(1)
        comparable[f"{field}_change"] = comparable[field] - comparable[f"prior_{field}"]
    pairs = comparable.dropna(subset=["prior_accession_number"]).copy()
    pairs = pairs.loc[pairs["accession_number"].ne(pairs["prior_accession_number"])]
    candidate_pair_count = len(pairs)
    quality = protocol["pair_quality"]
    elapsed = (
        pd.to_datetime(pairs["accepted_at"], utc=True)
        - pd.to_datetime(pairs["prior_accepted_at"], utc=True)
    ).dt.days
    denominator = pairs["prior_midpoint"].abs()
    denominator = denominator.where(denominator.ne(0))
    ratio = pairs["midpoint"].abs() / denominator
    plausible = (
        elapsed.between(1, quality["maximum_days_between_revisions"])
        & ratio.between(quality["minimum_midpoint_ratio"], quality["maximum_midpoint_ratio"])
    )
    plausible &= ~(
        pairs["metric"].eq("EPS")
        & pairs[["prior_lower_bound", "prior_upper_bound", "lower_bound", "upper_bound"]].abs().max(axis=1).gt(quality["maximum_absolute_eps"])
    )
    plausible &= ~(
        pairs["metric"].eq("MARGIN")
        & ~pairs[["prior_lower_bound", "prior_upper_bound", "lower_bound", "upper_bound"]].apply(
            lambda column: column.between(quality["minimum_margin_percent"], quality["maximum_margin_percent"])
        ).all(axis=1)
    )
    pairs = pairs.loc[plausible.fillna(False)].copy()
    quality_rejected_pair_count = candidate_pair_count - len(pairs)
    pairs["guidance_direction"] = "NOT_CLASSIFIED"
    pairs["pair_status"] = "AUTOMATED_CANDIDATE_NOT_SOURCE_VERIFIED"
    years = pd.to_datetime(pairs["accepted_at"], utc=True).dt.year if not pairs.empty else pd.Series(dtype=int)
    gate = protocol["coverage_gate"]
    stats = {
        "comparable_pairs": len(pairs),
        "source_verified_comparable_pairs": 0,
        "tickers_with_pairs": int(pairs["ticker"].nunique()) if not pairs.empty else 0,
        "calendar_years_with_pairs": int(years.nunique()),
        "metrics_with_pairs": int(pairs["metric"].nunique()) if not pairs.empty else 0,
    }
    passed = (
        stats["comparable_pairs"] >= gate["minimum_comparable_pairs"]
        and stats["tickers_with_pairs"] >= gate["minimum_tickers_with_pairs"]
        and stats["calendar_years_with_pairs"] >= gate["minimum_calendar_years_with_pairs"]
        and stats["metrics_with_pairs"] >= gate["minimum_metrics_with_pairs"]
    )
    manifest = corpus / "manifest.json"
    report = {
        "report_version": "herd-sec-guidance-normalization-v1",
        "snapshot_id": json.loads(manifest.read_text(encoding="utf-8"))["snapshot_id"],
        "snapshot_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "normalized_ranges": len(guidance),
        "normalized_tickers": int(guidance["ticker"].nunique()) if not guidance.empty else 0,
        "explicit_basis_ranges": int(guidance["accounting_basis"].ne("UNSPECIFIED").sum()) if not guidance.empty else 0,
        "candidate_like_for_like_pairs": candidate_pair_count,
        "quality_rejected_pairs": quality_rejected_pair_count,
        **stats,
        "coverage_gate": gate,
        "coverage_gate_passed": passed,
        "normalization_quality_review_required": passed,
        "ready_for_direction_preregistration": False,
        "next_decision": "QUALITY_REVIEW_REQUIRED_BEFORE_DIRECTION_PREREGISTRATION" if passed else "COVERAGE_BLOCKED",
        "guidance_direction_classified": 0,
        "operational_action_ratio": 0.0,
        "limitations": [
            "Normalization uses conservative lexical rules and excludes implicit fiscal periods.",
            "UNSPECIFIED accounting basis is retained for audit but excluded from comparable pairs.",
            "A comparable pair is not evidence that a revision predicts future drawdown.",
            "Passing the mechanical coverage gate does not establish parser precision; stratified source review is required.",
            "Flattened HTML tables can place a metric, fiscal period, and range from different cells near each other.",
            "Comparable-pair rows are automated review candidates, not source-verified revisions.",
            "Direction and materiality tolerances remain unassigned."
        ],
    }
    guidance["accepted_at"] = guidance["accepted_at"].astype(str)
    pairs["accepted_at"] = pairs["accepted_at"].astype(str)
    pairs["prior_accepted_at"] = pairs["prior_accepted_at"].astype(str)
    return guidance, pairs, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ranges", type=Path, required=True)
    parser.add_argument("--pairs", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    ranges, pairs, report = normalize(Path(protocol["corpus"]), protocol)
    args.ranges.parent.mkdir(parents=True, exist_ok=True)
    ranges.to_csv(args.ranges, index=False, float_format="%.12g", lineterminator="\n")
    pairs.to_csv(args.pairs, index=False, float_format="%.12g", lineterminator="\n")
    report["protocol_sha256"] = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
