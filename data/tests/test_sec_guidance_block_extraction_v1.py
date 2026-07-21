from pathlib import Path

from herd.sec_guidance_block_extraction_v1 import (
    extract_block_candidates,
    load_aliases,
    structured_blocks,
    select_stratified_review,
)
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
ALIASES = load_aliases(ROOT / "herd/sec_guidance_metric_aliases_v1.csv")


def test_preserves_ascii_paragraph_boundaries():
    blocks = structured_blocks(b"First line\nsecond line\n\nNext paragraph\n")
    assert [block["block_text"] for block in blocks] == ["First line\nsecond line", "Next paragraph"]
    assert all(block["source_kind"] == "ASCII" for block in blocks)


def test_preserves_html_paragraph_and_single_cell_row_boundaries():
    blocks = structured_blocks(b"<html><p>Paragraph guidance</p><table><tr><td>Row guidance</td></tr></table></html>")
    values = {(block["source_kind"], block["block_text"]) for block in blocks}
    assert ("HTML_P", "Paragraph guidance") in values
    assert ("HTML_SINGLE_CELL_ROW", "Row guidance") in values


def test_issuer_scoped_adjusted_ebitda_alias():
    text = "For full-year 2026, adjusted EBITDA guidance is $10.2 to $10.4 billion."
    row = extract_block_candidates(text, "TMUS", ALIASES)[0]
    assert row["metric"] == "ADJUSTED_EBITDA"
    assert row["accounting_basis"] == "NON_GAAP"
    assert extract_block_candidates(text, "AAPL", ALIASES) == []


def test_keeps_reit_affo_separate_from_operating_income():
    text = "For FY 2026, AFFO guidance is $5.20 to $5.40 per share."
    row = extract_block_candidates(text, "AMT", ALIASES)[0]
    assert row["metric"] == "AFFO"
    assert row["unit"] == "USD_PER_SHARE"


def test_organic_sales_is_percent_not_revenue_dollars():
    text = "For full-year 2026, organic sales growth guidance is 4 to 6 percent."
    row = extract_block_candidates(text, "PEP", ALIASES)[0]
    assert row["metric"] == "ORGANIC_REVENUE_GROWTH"
    assert row["unit"] == "PERCENT"


def test_capex_does_not_inherit_non_gaap_from_adjusted_eps_in_same_block():
    text = "For FY 2026 adjusted EPS guidance is $4.20 to $4.50 per share. Capital expenditures guidance is $5 to $6 billion."
    rows = extract_block_candidates(text, "APD", ALIASES)
    capex = next(row for row in rows if row["metric"] == "CAPEX")
    assert capex["accounting_basis"] == "NOT_APPLICABLE"


def test_does_not_use_period_after_range():
    text = "Revenue guidance is $10 to $11 billion compared with FY 2025."
    assert extract_block_candidates(text, "AAPL", ALIASES) == []


def test_rejects_midpoint_change_amounts_as_ranges():
    text = "For full-year 2026 outlook, we are raising the AFFO midpoint by $5 million and $10 million, respectively."
    assert extract_block_candidates(text, "AMT", ALIASES) == []


def test_marks_explicit_previous_range_as_prior_reference():
    text = "For full-year 2026, adjusted EBITDA guidance is now $10.2 to $10.4 billion, above the previous range of $9.8 to $10.1 billion."
    rows = extract_block_candidates(text, "TMUS", ALIASES)
    assert [row["range_role"] for row in rows] == ["CURRENT_CANDIDATE", "PRIOR_REFERENCE"]


def test_rejects_distant_alias_association_in_large_block():
    text = "For FY 2026 revenue guidance " + ("unrelated text " * 30) + "$10 to $11 billion."
    assert extract_block_candidates(text, "AAPL", ALIASES) == []


def test_review_sampling_seeds_each_issuer_before_metric_fill():
    rows = []
    for index, ticker in enumerate(["A", "B", "C"]):
        rows.append({"ticker": ticker, "metric": "EPS", "range_role": "CURRENT_CANDIDATE", "review_priority": f"{index:02d}"})
    rows.append({"ticker": "A", "metric": "REVENUE", "range_role": "CURRENT_CANDIDATE", "review_priority": "99"})
    review = select_stratified_review(pd.DataFrame(rows), 2)
    assert review["ticker"].nunique() == 3
    assert set(review["metric"]) == {"EPS", "REVENUE"}
