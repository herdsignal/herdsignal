import json
from pathlib import Path

import pandas as pd

from herd.expectation_evidence_oos_v1 import _outcome, _trading_sessions_between


ROOT = Path(__file__).resolve().parents[1]


def test_trim_outcome_is_relative_to_buy_and_hold_and_costed():
    prices = pd.DataFrame(
        {"Adj Close": [100.0, 90.0, 80.0, 70.0]},
        index=pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07"]),
    )
    outcome = _outcome(prices, pd.Timestamp("2020-01-01"), 3, 0.05, 15)
    assert round(outcome["trim_uplift"], 6) == round(0.05 * 0.30 - 0.05 * 0.0015, 6)
    assert outcome["drawdown_relief"] == outcome["trim_uplift"]


def test_protocol_forbids_test_threshold_and_operational_sell():
    protocol = json.loads((ROOT / "herd/expectation_evidence_oos_v1.json").read_text())
    assert protocol["trim_ratio"] == 0.05
    assert "TEST_DERIVED_THRESHOLD" in protocol["forbidden"]
    assert "ACTIVATE_OPERATIONAL_SELL" in protocol["forbidden"]


def test_cooldown_counts_trading_sessions_not_calendar_days():
    prices = pd.DataFrame(index=pd.bdate_range("2020-01-01", periods=10))
    assert _trading_sessions_between(prices, pd.Timestamp("2020-01-01"), pd.Timestamp("2020-01-08")) == 5
