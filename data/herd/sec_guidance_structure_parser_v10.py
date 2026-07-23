"""V9 독립 검수에서 확인된 여섯 일반 문법을 교정하는 마지막 증분 파서."""

from __future__ import annotations

import re

import pandas as pd

from herd.sec_guidance_structure_parser_v5 import _context
from herd.sec_guidance_structure_parser_v7 import _matching_range
from herd.sec_guidance_structure_parser_v9 import transform_candidate as transform_v9


FORWARD_FULL_YEAR_HEADER = re.compile(r"\bfull[- ]year\s+(20\d{2})\s+guidance\b", re.I)
NARRATIVE_NON_GAAP_EPS = re.compile(
    r"\bnon[- ]GAAP\s+(?:adjusted\s+)?(?:diluted\s+)?EPS\b.{0,60}$",
    re.I | re.S,
)
REPORTED_EPS_ROW = re.compile(
    r"\breported\s+(?:fully\s+)?diluted\s+(?:earnings\s+per\s+share|EPS)\b",
    re.I,
)
EXCLUDING_ITEMS_AFTER = re.compile(
    r"^.{0,80}\bexcluding\b.{0,80}\b(?:restructuring|one[- ]time|special|specified)\b",
    re.I | re.S,
)
ANNUAL_GUIDANCE_ACTION = re.compile(
    r"\b(?:narrowing|raising|lowering|maintaining|reaffirming)\b.{0,40}"
    r"\b(?:our\s+)?(20\d{2})\b.{0,50}\bguidance\b",
    re.I | re.S,
)
PREVIOUS_PRELIMINARY = re.compile(r"\bhad\s+provided\s+preliminary\s+guidance\b", re.I)


def transform_candidate(row: pd.Series) -> dict | None:
    transformed = transform_v9(row)
    if transformed is None:
        return None
    item = dict(transformed)
    candidate = pd.Series(item)
    context = _context(candidate)
    match = _matching_range(candidate, context)
    if match is None:
        return None

    before = context[max(0, match.start() - 1_200):match.start()]
    after = context[match.end():match.end() + 180]
    row_header = str(candidate.get("row_header", ""))

    if PREVIOUS_PRELIMINARY.search(before):
        return None

    full_year = list(FORWARD_FULL_YEAR_HEADER.finditer(before))
    if full_year:
        item["fiscal_period"] = f"FY{full_year[-1].group(1)}"
    annual_action = list(ANNUAL_GUIDANCE_ACTION.finditer(before))
    if annual_action:
        item["fiscal_period"] = f"FY{annual_action[-1].group(1)}"

    if NARRATIVE_NON_GAAP_EPS.search(before):
        item["accounting_basis"] = "NON_GAAP"
    # "reported EPS guidance" alone does not prove GAAP.  Treat it as GAAP
    # only when the source itself frames the table as a reported-basis
    # reconciliation; this keeps the rule structural rather than issuer based.
    if (
        REPORTED_EPS_ROW.search(row_header)
        and re.search(r"\boutlook\s+reconciliation\b", context, re.I)
        and re.search(r"\breported\s*basis\b", context, re.I)
    ):
        item["accounting_basis"] = "GAAP"
    if EXCLUDING_ITEMS_AFTER.search(after):
        item["accounting_basis"] = "NON_GAAP"

    item["candidate_status"] = "V10_SIX_GRAMMAR_CORRECTED_NOT_SOURCE_REVIEWED"
    return item


def audit_v9_review(path: str) -> dict:
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
        "v9_invalid_audited": len(invalid),
        "v9_invalid_dropped": dropped,
        "v9_invalid_corrected": corrected,
        "v9_invalid_unchanged": unchanged,
        "v9_valid_audited": len(valid),
        "v9_valid_retained": retained,
        "v9_valid_changed": changed,
        "v10_development_regression_passed": (
            repaired >= 5 and unchanged == 0 and retained == len(valid) and changed == 0
        ),
    }
