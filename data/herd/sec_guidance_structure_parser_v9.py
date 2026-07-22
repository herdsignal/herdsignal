"""V8 독립 검수에서 확인된 일곱 구조 문법만 교정한다."""

from __future__ import annotations

import re

import pandas as pd

from herd.sec_guidance_structure_parser_v5 import _context, _normalized_ranges, _same_bounds
from herd.sec_guidance_structure_parser_v7 import _matching_range
from herd.sec_guidance_structure_parser_v8 import transform_candidate as transform_v8


EPS_BRIDGE = re.compile(
    r"\bguidance\s+basis\s+earnings\s+per\s+share\b.{0,240}"
    r"\b(?:drivers?|O&M\s+management|rate\s+relief)\b",
    re.I | re.S,
)
SHARE_COUNT = re.compile(r"\bweighted\s+average\s+share\s+count\b", re.I)
NON_GAAP_ROW = re.compile(r"\bnon[- ]GAAP\s+(?:diluted\s+)?EPS\b", re.I)
GAAP_ROW = re.compile(r"(?<!non[- ])\bGAAP\s+(?:diluted\s+)?EPS\b", re.I)
PARENTHETICAL_WAS = re.compile(r"\(\s*was\b[^)]*$", re.I | re.S)
PREVIOUSLY_ANNOUNCED = re.compile(r"\bpreviously\s+announced\s+guidance\b", re.I)
CURRENT_CONFIRMATION = re.compile(
    r"\b(?:reaffirm(?:s|ed|ing)?|maintain(?:s|ed|ing)?|unchanged|no\s+changes?)\b",
    re.I,
)
REAFFIRMED_ANNUAL = re.compile(
    r"\b(?:re)?affirm(?:s|ed|ing)?\b.{0,60}\b(20\d{2})\b.{0,60}\bguidance\b",
    re.I | re.S,
)
RESPECTIVELY = re.compile(r"\brespectively\b", re.I)
DILUTED_AND_ADJUSTED_EPS = re.compile(
    r"\bdiluted\s+EPS\d*\b.{0,80}\band\s+adjusted\s+diluted\s+EPS\d*\b",
    re.I | re.S,
)


def _bind_respectively_basis(row: pd.Series, item: dict, source_excerpt: str) -> None:
    if not (RESPECTIVELY.search(source_excerpt) and DILUTED_AND_ADJUSTED_EPS.search(source_excerpt)):
        return
    ranges = _normalized_ranges(source_excerpt, str(row["unit"]))
    unique: list[tuple[float, float]] = []
    for _, low, high in ranges:
        if (low, high) not in unique:
            unique.append((low, high))
    matching = [index for index, (low, high) in enumerate(unique) if _same_bounds(row, low, high)]
    if len(unique) < 2 or not matching:
        return
    if matching[0] == 0:
        item["accounting_basis"] = "UNSPECIFIED"
    elif matching[0] == 1:
        item["accounting_basis"] = "NON_GAAP"


def transform_candidate(row: pd.Series) -> dict | None:
    transformed = transform_v8(row)
    if transformed is None:
        return None
    item = dict(transformed)
    candidate = pd.Series(item)
    context = _context(candidate)
    match = _matching_range(candidate, context)
    if match is None:
        return None

    before = context[max(0, match.start() - 1_200):match.start()]
    row_header = str(candidate.get("row_header", ""))
    source_excerpt = str(candidate.get("source_excerpt", ""))

    if EPS_BRIDGE.search(source_excerpt):
        return None
    if SHARE_COUNT.search(row_header):
        return None
    if PARENTHETICAL_WAS.search(before):
        return None
    if PREVIOUSLY_ANNOUNCED.search(before) and not CURRENT_CONFIRMATION.search(source_excerpt):
        return None

    _bind_respectively_basis(candidate, item, source_excerpt)
    if NON_GAAP_ROW.search(row_header):
        item["accounting_basis"] = "NON_GAAP"
    elif GAAP_ROW.search(row_header):
        item["accounting_basis"] = "GAAP"

    reaffirmed = list(REAFFIRMED_ANNUAL.finditer(before))
    if reaffirmed:
        item["fiscal_period"] = f"FY{reaffirmed[-1].group(1)}"

    item["candidate_status"] = "V9_SEVEN_GRAMMAR_CORRECTED_NOT_SOURCE_REVIEWED"
    return item


def audit_v8_review(path: str) -> dict:
    reviewed = pd.read_csv(path, dtype={"cik": str})
    semantic = ("fiscal_period", "accounting_basis", "metric", "unit", "lower_bound", "upper_bound")
    invalid = reviewed.loc[reviewed["review_decision"].eq("INVALID")]
    valid = reviewed.loc[reviewed["review_decision"].eq("VALID")]
    dropped = corrected = unchanged = 0
    for _, row in invalid.iterrows():
        transformed = transform_candidate(row)
        if transformed is None:
            dropped += 1
        elif all(str(transformed[field]) == str(row[field]) for field in semantic):
            unchanged += 1
        else:
            corrected += 1
    retained = changed = 0
    for _, row in valid.iterrows():
        transformed = transform_candidate(row)
        if transformed is None:
            continue
        retained += 1
        if any(str(transformed[field]) != str(row[field]) for field in semantic):
            changed += 1
    repaired = dropped + corrected
    return {
        "v8_invalid_audited": len(invalid),
        "v8_invalid_dropped": dropped,
        "v8_invalid_corrected": corrected,
        "v8_invalid_unchanged": unchanged,
        "v8_valid_audited": len(valid),
        "v8_valid_retained": retained,
        "v8_valid_changed": changed,
        "v9_development_regression_passed": (
            repaired >= 7 and unchanged == 0 and retained == len(valid) and changed == 0
        ),
    }
