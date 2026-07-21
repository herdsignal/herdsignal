from pathlib import Path

from herd.sec_guidance_block_extraction_v1 import load_aliases
from herd.sec_guidance_structure_parser_v2 import parse_block_v2


ROOT = Path(__file__).resolve().parents[1]
ALIASES = load_aliases(ROOT / "herd/sec_guidance_metric_aliases_v1.csv")


def current(text, ticker="AMT"):
    return [row for row in parse_block_v2(text, ticker, ALIASES) if row["semantic_role"] == "CURRENT_GUIDANCE_RANGE" and row["range_role"] == "CURRENT_CANDIDATE"]


def test_respectively_maps_ranges_to_their_own_metrics():
    text = "For full-year 2026 guidance, we expect total property revenue, net income and Adjusted EBITDA of $6.3 to $6.4 billion, $1.2 to $1.3 billion and $3.9 to $4.0 billion, respectively."
    rows = current(text)
    assert [(row["metric"], row["lower_bound"]) for row in rows] == [("REVENUE", 6.3e9), ("ADJUSTED_EBITDA", 3.9e9)]


def test_midpoint_and_impact_amounts_are_not_current_ranges():
    midpoint = "For full-year 2026 outlook, we raise Adjusted EBITDA midpoint by $30 million and $70 million."
    impact = "For full-year 2026 outlook, Adjusted EBITDA has an unfavorable impact of $30 million to $70 million."
    assert current(midpoint, "TMUS") == []
    assert current(impact, "TMUS") == []


def test_long_respectively_midpoint_sentence_is_not_a_range():
    text = "The Company is raising the midpoints of its full year 2026 outlook for property revenue, Adjusted EBITDA, AFFO and AFFO per Share by $145 million, $105 million, $55 million and $0.12, respectively."
    assert current(text, "AMT") == []


def test_from_old_to_new_marks_only_new_range_current():
    text = "For full-year 2026 adjusted EPS guidance, we increased from $4.10 to $4.20 to $4.30 to $4.40 per share."
    rows = parse_block_v2(text, "LLY", ALIASES)
    assert [row["range_role"] for row in rows] == ["PRIOR_REFERENCE", "CURRENT_CANDIDATE"]


def test_current_range_followed_by_from_prior_range_marks_prior_reference():
    text = "Full-year 2026 adjusted EPS guidance is $4.30 to $4.40 per share from $4.10 to $4.20 per share."
    rows = parse_block_v2(text, "LLY", ALIASES)
    assert [row["range_role"] for row in rows] == ["CURRENT_CANDIDATE", "PRIOR_REFERENCE"]


def test_reconciliation_component_amounts_are_not_guidance_ranges():
    text = "Our full-year 2026 non-GAAP outlook reflects adjustments for amortization of $150 million to $170 million."
    assert current(text, "V") == []


def test_quarter_and_full_year_periods_are_range_local():
    text = "For first quarter fiscal year 2026 adjusted EPS guidance is $2.10 to $2.20 per share. Full-year 2026 adjusted EPS guidance is $9.10 to $9.30 per share."
    rows = current(text, "APD")
    assert [row["fiscal_period"] for row in rows] == ["Q1-2026", "FY2026"]


def test_basis_is_attached_to_each_range():
    text = "Full-year 2026 EPS guidance is $3.10 to $3.20 on a reported basis and $4.10 to $4.20 on a non-GAAP basis."
    rows = current(text, "LLY")
    assert [row["accounting_basis"] for row in rows] == ["GAAP", "NON_GAAP"]


def test_cash_capex_keeps_capitalized_interest_subtype():
    text = "For full-year 2026 guidance, cash capital expenditures excluding capitalized interest are $5.0 to $5.2 billion and cash capital expenditures including capitalized interest are $5.4 to $5.6 billion."
    rows = current(text, "TMUS")
    assert [row["metric_subtype"] for row in rows] == ["EXCLUDING_CAPITALIZED_INTEREST", "INCLUDING_CAPITALIZED_INTEREST"]


def test_malformed_multiline_currency_token_is_skipped():
    text = "For FY 2026 revenue guidance is $10 to $\n\n-\n\n597 million."
    assert current(text, "AAPL") == []


def test_historical_range_without_guidance_context_is_skipped():
    text = "Full-year 2026 revenue was $10.0 to $10.2 billion following strong demand."
    assert current(text, "AAPL") == []


def test_table_row_can_inherit_guidance_header_context():
    text = "Full-year 2026 outlook\nRevenue $10.0 to $10.2 billion"
    rows = current(text, "AAPL")
    assert [(row["metric"], row["fiscal_period"]) for row in rows] == [("REVENUE", "FY2026")]
