"""V6 원문 검수에서 확인된 네 구조 관계만 교정한다."""

from __future__ import annotations

import re

import pandas as pd

from herd.sec_guidance_structure_parser_v5 import _context, _normalized_ranges, _same_bounds


ADJUSTED_AFTER = re.compile(r"^\s*(?:on\s+an?\s+)?adjusted\s+basis\b", re.I)
ADJUSTED_BEFORE = re.compile(r"\badjusted(?:\s+diluted)?\s+(?:earnings per share|EPS)\b", re.I)
EXCLUDING_ITEMS = re.compile(r"\bexcluding\s+(?:specified|special)\s+items\b", re.I)
GAAP_BEFORE = re.compile(r"\bGAAP\s+(?:earnings per share|EPS)\b", re.I)
QUALITATIVE_HIGH_END = re.compile(r"\b(?:at|in)\s+(?:the\s+)?(?:high|upper)\s+end\s+of\b", re.I)
QUARTER_NEAR = re.compile(r"\b(first|second|third|fourth)\s+quarter\s+(?:EPS|earnings per share)\b", re.I)
YEAR = re.compile(r"\b(?:full\s+year|fiscal\s+year)\s+(20\d{2})\b", re.I)
WORDS = {"first": 1, "second": 2, "third": 3, "fourth": 4}
OPERATING_CASH_FLOW = re.compile(r"\boperating\s+cash\s+flow\b", re.I)


def _matching_range(row: pd.Series, context: str):
    matches = [entry for entry in _normalized_ranges(context, str(row["unit"])) if _same_bounds(row, entry[1], entry[2])]
    return matches[-1][0] if matches else None


def transform_candidate(row: pd.Series) -> dict | None:
    item = row.to_dict()
    context = _context(row)
    match = _matching_range(row, context)
    if match is None:
        return None
    if QUALITATIVE_HIGH_END.search(context[:match.start()]):
        return None
    if str(row.get("metric")) == "FREE_CASH_FLOW" and OPERATING_CASH_FLOW.search(
        " ".join((str(row.get("row_header", "")), context))
    ):
        return None

    before = context[max(0, match.start() - 500):match.start()]
    after = context[match.end():match.end() + 60]
    adjusted = list(ADJUSTED_BEFORE.finditer(before))
    gaap = list(GAAP_BEFORE.finditer(before))
    if ADJUSTED_AFTER.search(after) or EXCLUDING_ITEMS.search(before) or (adjusted and (not gaap or adjusted[-1].start() > gaap[-1].start())):
        item["accounting_basis"] = "NON_GAAP"
    elif gaap:
        item["accounting_basis"] = "GAAP"

    # 동일 문장에 연간과 분기 범위가 함께 있을 때 해당 범위 직전의 마지막 기간 역할을 사용한다.
    quarters = list(QUARTER_NEAR.finditer(before))
    if quarters:
        years = list(YEAR.finditer(context))
        if not years:
            return None
        year = years[0].group(1)
        item["fiscal_period"] = f"Q{WORDS[quarters[-1].group(1).lower()]}-{year}"

    item["candidate_status"] = "V7_FOUR_RELATION_CORRECTED_NOT_SOURCE_REVIEWED"
    return item


def audit_v6_review(path: str) -> dict:
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
    retained = sum(transform_candidate(row) is not None for _, row in valid.iterrows())
    return {
        "v6_nonvalid_audited": len(nonvalid), "v6_nonvalid_dropped": dropped,
        "v6_nonvalid_corrected": corrected, "v6_nonvalid_unchanged": unchanged,
        "v6_valid_audited": len(valid), "v6_valid_retained": retained,
        "v7_development_regression_passed": unchanged == 0 and retained == len(valid),
    }
