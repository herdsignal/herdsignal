import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from herd.systematic_healthy_pullback_v1 import decompose, group_label, latest_prior_business, load_protocol


def test_unknown_business_never_becomes_healthy():
    protocol = load_protocol()
    assert group_label("UNKNOWN", 0.9, protocol) == "EXCLUDED_UNKNOWN_OR_MIDDLE"


def test_only_prior_month_business_state_is_visible():
    business = pd.DataFrame({"ticker": ["A", "A"], "month_end": pd.to_datetime(["2020-01-31", "2020-02-29"]), "guard_state": ["PASS", "VETO"]})
    result = latest_prior_business(business, "A", pd.Timestamp("2020-02-14"))
    assert result["guard_state"] == "PASS"


def test_prelocked_source_buckets_leave_middle_unclassified():
    protocol = load_protocol()
    assert group_label("PASS", 0.8, protocol) == "HEALTHY_SYSTEMATIC"
    assert group_label("PASS", 0.2, protocol) == "HEALTHY_FIRM_SPECIFIC"
    assert group_label("PASS", 0.5, protocol) == "EXCLUDED_UNKNOWN_OR_MIDDLE"
    assert protocol["adoption_gate"]["required_passed_contrasts"] == 2


def test_stock_specific_intercept_is_not_counted_as_market_or_sector():
    protocol = load_protocol()
    dates = pd.bdate_range("2019-01-01", periods=300)
    market_returns = np.sin(np.arange(299)) * 0.002
    stock_returns = market_returns + 0.001

    def frame(returns):
        close = 100 * np.exp(np.r_[0, np.cumsum(returns)])
        return pd.DataFrame({"Date": dates, "Adj Close": close})

    result = decompose(frame(stock_returns), frame(market_returns), frame(market_returns), dates[-1], protocol)
    assert abs(result["common_return_63d"] - market_returns[-63:].sum()) < 1e-8
    assert result["residual_return_63d"] > 0.06


def test_admission_registry_pins_rejected_artifacts():
    root = Path(__file__).resolve().parents[2]
    registry = json.loads((root / "data/herd/evidence_admission_registry_v4.json").read_text())
    assert registry["decision"]["reentry_evidence_admitted"] is False
    for item in registry["source_artifacts"]:
        assert hashlib.sha256((root / item["path"]).read_bytes()).hexdigest() == item["sha256"]
