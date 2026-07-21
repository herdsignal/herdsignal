import json
from pathlib import Path

from herd.sec_guidance_normalization_v1 import extract_ranges


ROOT = Path(__file__).resolve().parents[1]


def test_extracts_explicit_like_for_like_adjusted_eps_range():
    rows = extract_ranges(
        "For FY 2026, the company expects adjusted EPS in the range of $4.20 to $4.50 per share."
    )
    assert len(rows) == 1
    assert rows[0]["metric"] == "EPS"
    assert rows[0]["fiscal_period"] == "FY2026"
    assert rows[0]["accounting_basis"] == "NON_GAAP"
    assert rows[0]["unit"] == "USD_PER_SHARE"
    assert rows[0]["lower_bound"] == 4.2
    assert rows[0]["upper_bound"] == 4.5


def test_normalizes_shared_billion_scale_for_revenue():
    rows = extract_ranges(
        "Our FY 2025 outlook: we expect revenue from $10.0 to $10.5 billion."
    )
    assert rows[0]["lower_bound"] == 10_000_000_000
    assert rows[0]["upper_bound"] == 10_500_000_000


def test_rejects_implicit_period_and_single_point_guidance():
    assert extract_ranges("We expect adjusted EPS of $4.20 next year.") == []


def test_does_not_assign_eps_sized_range_to_nearby_revenue():
    rows = extract_ranges(
        "For FY 2025 our outlook includes revenue and adjusted EPS in a range of $4.20 to $4.50."
    )
    assert [row["metric"] for row in rows] == ["EPS"]


def test_rejects_unscaled_currency_range_for_dollar_metrics():
    assert extract_ranges("For FY 2025 we expect revenue of $4.20 to $4.50.") == []


def test_protocol_forbids_direction_before_preregistration():
    protocol = json.loads((ROOT / "herd/sec_guidance_normalization_v1.json").read_text())
    assert "ASSIGN_UP_DOWN_FLAT_BEFORE_PREREGISTRATION" in protocol["forbidden"]
    assert "COMPARE_GAAP_WITH_NON_GAAP" in protocol["forbidden"]
    assert protocol["pair_quality"]["maximum_midpoint_ratio"] == 2.0
    assert "PRICE_OUTCOME" in protocol["protocol_revision_reason"]
    assert protocol["promotion_contract"]["automated_pairs_are_candidates_only"] is True
