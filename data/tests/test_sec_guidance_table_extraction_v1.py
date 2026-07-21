import json
from pathlib import Path

from lxml import html

from herd.sec_guidance_table_extraction_v1 import expand_table, extract_table_candidates


ROOT = Path(__file__).resolve().parents[1]


def test_expands_rowspan_and_colspan_without_flattening_rows():
    table = html.fromstring("""
      <table><tr><th rowspan='2'>Metric</th><th colspan='2'>FY 2026 Guidance</th></tr>
      <tr><th>Low</th><th>High</th></tr><tr><td>Revenue</td><td>10</td><td>11</td></tr></table>
    """)
    assert expand_table(table) == [
        ["Metric", "FY 2026 Guidance", "FY 2026 Guidance"],
        ["Metric", "Low", "High"],
        ["Revenue", "10", "11"],
    ]


def test_extracts_metric_range_and_period_from_same_row_and_column_header():
    rows = extract_table_candidates(b"""
      <html><table><tr><th>Metric</th><th>FY 2026 Guidance</th></tr>
      <tr><td>Adjusted EPS</td><td>$4.20 to $4.50 per share</td></tr></table></html>
    """)
    assert len(rows) == 1
    assert rows[0]["metric"] == "EPS"
    assert rows[0]["fiscal_period"] == "FY2026"
    assert rows[0]["accounting_basis"] == "NON_GAAP"
    assert rows[0]["lower_bound"] == 4.2


def test_does_not_link_metric_and_range_across_rows():
    rows = extract_table_candidates(b"""
      <html><table><tr><th>FY 2026 Guidance</th></tr>
      <tr><td>Revenue</td></tr><tr><td>$4.20 to $4.50 billion</td></tr></table></html>
    """)
    assert rows == []


def test_does_not_use_comparison_period_after_guidance_range():
    rows = extract_table_candidates(b"""
      <html><table><tr><td>Outlook</td></tr><tr><td>
      Net sales are expected to be between $69 billion and $73 billion,
      compared with first quarter 2019.</td></tr></table></html>
    """)
    assert rows == []


def test_does_not_treat_growth_percent_as_eps_range():
    rows = extract_table_candidates(b"""
      <html><table><tr><td>Guidance</td></tr><tr><td>
      FY 2026 adjusted EPS guidance is $7.25 to $7.50, up 10 to 14 percent.</td></tr></table></html>
    """)
    assert len(rows) == 1
    assert rows[0]["lower_bound"] == 7.25


def test_protocol_locks_review_before_direction_labels():
    protocol = json.loads((ROOT / "herd/sec_guidance_table_extraction_v1.json").read_text())
    assert protocol["review_gate"]["minimum_stratified_rows"] == 60
    assert "INFER_DIRECTION_BEFORE_REVIEW_AND_COVERAGE_GATES" in protocol["forbidden"]
