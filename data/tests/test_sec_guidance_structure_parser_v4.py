from pathlib import Path

from lxml import html

from herd.sec_guidance_block_extraction_v1 import load_aliases
from herd.sec_guidance_structure_parser_v4 import _narrative_binding, _table_bindings, parse_document_v4
from herd.sec_guidance_structure_v4_regression_audit import audit


ROOT = Path(__file__).resolve().parents[2]
ALIASES = load_aliases(ROOT / "data/herd/sec_guidance_metric_aliases_v1.csv")


def test_table_grid_binds_latest_column_and_multilevel_header() -> None:
    source = b"""
    <html><body><h2>Fiscal year 2024 guidance</h2><table>
      <tr><th rowspan='2'>Metric</th><th colspan='2'>Fiscal 2024 outlook</th></tr>
      <tr><th>Prior as of March 21, 2024</th><th>Revised as of June 21, 2024</th></tr>
      <tr><td>Adjusted operating margin</td><td>36.3% - 36.7%</td><td>37.0% - 37.5%</td></tr>
    </table></body></html>
    """
    rows = _table_bindings(source, "FDS", ALIASES)
    assert len(rows) == 1
    assert rows[0]["metric"] == "MARGIN"
    assert rows[0]["accounting_basis"] == "NON_GAAP"
    assert rows[0]["fiscal_period"] == "FY2024"
    assert rows[0]["lower_bound"] == 37.0
    assert rows[0]["column_index"] == 2
    assert "Revised" in rows[0]["header_path"]


def test_narrative_update_keeps_only_new_range() -> None:
    text = (
        "For fiscal year 2025, the Company is updating its revenue guidance from a range of "
        "$23.5 billion to $25.0 billion to a new range of $21.8 billion to $22.6 billion."
    )
    rows = _narrative_binding(text, "SMCI", ALIASES)
    assert len(rows) == 1
    assert rows[0]["lower_bound"] == 21.8e9
    assert rows[0]["upper_bound"] == 22.6e9
    assert rows[0]["numeric_role"] == "CURRENT_GUIDANCE_RANGE"


def test_reporting_period_is_not_reused_as_guidance_period() -> None:
    text = "First quarter 2025 results were reported. The company expects adjusted EPS of $1.48 to $1.52."
    assert _narrative_binding(text, "PCG", ALIASES) == []


def test_respectively_single_values_are_not_merged_into_range() -> None:
    text = (
        "For fiscal year 2017, guidance expects second-half and full-year capital expenditures "
        "of $1.0 billion and $2.6 billion, respectively."
    )
    assert _narrative_binding(text, "LUMN", ALIASES) == []


def test_table_without_unambiguous_current_column_is_rejected() -> None:
    source = b"""
    <html><body><h2>Fiscal year 2024 guidance</h2><table>
      <tr><th>Metric</th><th>Scenario A</th><th>Scenario B</th></tr>
      <tr><td>Revenue</td><td>$2.1 billion - $2.2 billion</td><td>$2.2 billion - $2.3 billion</td></tr>
    </table></body></html>
    """
    assert _table_bindings(source, "FDS", ALIASES) == []


def test_flattened_slide_div_is_not_reparsed_as_narrative() -> None:
    source = b"""
    <html><body><div>Fiscal year 2024 guidance Revenue $2.1 billion to $2.2 billion
    Adjusted operating margin 36% to 37% EPS $15.00 to $16.00</div></body></html>
    """
    assert parse_document_v4(source, "FDS", ALIASES) == []


def test_v3_invalid_bindings_do_not_survive_v4_regression() -> None:
    import pandas as pd

    v3 = pd.read_csv(ROOT / "data/reports/sec_guidance_structure_expansion_reviewed_v3.csv")
    v4 = pd.read_csv(ROOT / "data/reports/sec_guidance_structure_v4_candidates.csv")
    report = audit(v3, v4)
    assert report["v4_exact_invalid_bindings_retained"] == 0
    assert report["development_regression_passed"] is True
    assert report["independent_precision_inferred"] is False


def test_v4_holdout_sample_is_ready_but_not_source_approved() -> None:
    import json

    report = json.loads((ROOT / "data/reports/sec_guidance_structure_v4.json").read_text())
    assert report["fresh_review_rows"] == 80
    assert report["fresh_review_tickers"] == 23
    assert report["review_sample_gate_ready"] is True
    assert report["review_gate_passed"] is False
    assert report["operational_action_ratio"] == 0
