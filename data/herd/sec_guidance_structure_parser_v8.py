"""V7 원문 검수에서 확인된 다섯 구조 관계만 교정한다."""

from __future__ import annotations

import re

import pandas as pd

from herd.sec_guidance_structure_parser_v5 import _context
from herd.sec_guidance_structure_parser_v7 import _matching_range, transform_candidate as transform_v7


LAST_DISCLOSED = re.compile(r"\blast\s+publicly\s+disclosed\s+guidance\b", re.I)
UNCHANGED = re.compile(r"(?:^|\|)\s*(?:NC|unchanged)\s*(?:\||$)", re.I)
PRIOR_GUIDANCE_NEAR = re.compile(
    r"\bprior\b.{0,180}\b(?:guidance|EPS|earnings\s+per\s+share)\b.{0,120}$", re.I | re.S,
)
YEAR_ENDED = re.compile(
    r"\byear\s+ended\s+(?:[A-Za-z]+\s+\d{1,2},?\s+)?(20\d{2})\b", re.I,
)
AFFIRMED_YEAR = re.compile(
    r"\baffirm(?:s|ed|ing)?\b.{0,80}\b(20\d{2})\b.{0,80}\b(?:guidance|outlook)\b", re.I | re.S,
)
Q_OUTLOOK = re.compile(r"\bQ([1-4])\s+(20\d{2})\s+(?:outlook|guidance)\b", re.I)
REPORTING_QUARTER_ALIGNMENT = re.compile(
    r"\b(?:first|second|third|fourth)\s+quarter\s+20\d{2}\s+guidance\s+basis\s+EPS\b"
    r".{0,160}\baligned\s+with\s+our\s+EPS\s+guidance\s+range\b",
    re.I | re.S,
)
HISTORICAL_WITHIN_GUIDANCE = re.compile(r"\bwithin\s+(?:the\s+)?guidance\s+range(?:\s+of)?\s*$", re.I)


def transform_candidate(row: pd.Series) -> dict | None:
    transformed = transform_v7(row)
    if transformed is None:
        return None
    item = dict(transformed)
    candidate = pd.Series(item)
    context = _context(candidate)
    match = _matching_range(candidate, context)
    if match is None:
        return None

    before = context[max(0, match.start() - 1_200):match.start()]
    source_excerpt = str(candidate.get("source_excerpt", ""))
    header_path = str(candidate.get("header_path", ""))

    if LAST_DISCLOSED.search(header_path) and not UNCHANGED.search(source_excerpt):
        return None
    if PRIOR_GUIDANCE_NEAR.search(before):
        return None
    if str(candidate.get("unit")) == "USD_PER_SHARE" and "%" in match.group(0):
        return None
    if REPORTING_QUARTER_ALIGNMENT.search(context):
        return None
    if HISTORICAL_WITHIN_GUIDANCE.search(before):
        return None

    year_ended = list(YEAR_ENDED.finditer(header_path)) or list(YEAR_ENDED.finditer(before))
    quarter_outlook = list(Q_OUTLOOK.finditer(before))
    affirmed_year = list(AFFIRMED_YEAR.finditer(before))
    if year_ended:
        item["fiscal_period"] = f"FY{year_ended[-1].group(1)}"
    if quarter_outlook:
        item["fiscal_period"] = f"Q{quarter_outlook[-1].group(1)}-{quarter_outlook[-1].group(2)}"
    if affirmed_year:
        item["fiscal_period"] = f"FY{affirmed_year[-1].group(1)}"

    item["candidate_status"] = "V8_FIVE_RELATION_CORRECTED_NOT_SOURCE_REVIEWED"
    return item


def audit_v7_review(path: str) -> dict:
    reviewed = pd.read_csv(path, dtype={"cik": str})
    semantic = ("fiscal_period", "accounting_basis", "metric", "unit", "lower_bound", "upper_bound")
    nonvalid = reviewed.loc[reviewed["review_decision"].ne("VALID")]
    valid = reviewed.loc[reviewed["review_decision"].eq("VALID")]
    dropped = corrected = unchanged = 0
    for _, row in nonvalid.iterrows():
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
    return {
        "v7_nonvalid_audited": len(nonvalid), "v7_nonvalid_dropped": dropped,
        "v7_nonvalid_corrected": corrected, "v7_nonvalid_unchanged": unchanged,
        "v7_valid_audited": len(valid), "v7_valid_retained": retained,
        "v7_valid_changed": changed,
        "v8_development_regression_passed": unchanged == 0 and retained == len(valid) and changed == 0,
    }
