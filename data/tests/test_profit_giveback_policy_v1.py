import json
from pathlib import Path

import pandas as pd
import pytest

from herd.profit_giveback_policy_v1 import (
    ProfitGivebackPolicyV1Error,
    _policy_mask,
    _position_observations,
    _sparsify,
    load_contract,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "data/herd/profit_giveback_policy_v1.json"


def test_contract_keeps_sparse_action_and_zero_authority() -> None:
    contract = load_contract(CONTRACT)
    assert contract["execution_policy"]["trim_fraction_of_current_shares"] == 0.05
    assert contract["execution_policy"]["maximum_trim_events_per_ticker_year"] == 2
    assert contract["claim_boundary"]["operational_action_ratio"] == 0.0


def test_position_giveback_uses_only_prices_observed_since_entry() -> None:
    dates = pd.bdate_range("2020-01-02", periods=40)
    prices = pd.DataFrame(
        {
            "Date": dates,
            "Adj Close": [100.0] * 10 + [150.0] * 15 + [130.0] * 15,
        }
    )
    observation_dates = dates[[0, 9, 19, 29, 39]]
    rows = pd.DataFrame(
        {
            "signal_date": observation_dates,
            "last_observed_session": observation_dates,
            "HERD_STAGE": ["CALM", "DRIFT", "RUSH", "RUSH", "DRIFT"],
            "HERD_TRANSITION": ["NEUTRAL"] * 5,
        }
    )
    result = _position_observations(rows, prices, dates[0], dates[-1])
    assert result.iloc[-1]["PEAK_GAIN"] == pytest.approx(0.5)
    assert result.iloc[-1]["DRAWDOWN_FROM_PEAK"] == pytest.approx(-2 / 15)
    assert result.iloc[-1]["PROFIT_GIVEBACK_FRACTION"] == pytest.approx(0.4)


def test_service_policy_requires_recent_rush_and_breaking() -> None:
    contract = load_contract(CONTRACT)
    policy = next(
        item for item in contract["policies"] if item["id"] == "HERD_GIVEBACK_S1"
    )
    rows = pd.DataFrame(
        {
            "PEAK_GAIN": [0.5, 0.5, 0.5],
            "DRAWDOWN_FROM_PEAK": [-0.15, -0.15, -0.15],
            "PROFIT_GIVEBACK_FRACTION": [0.3, 0.3, 0.3],
            "RECENT_RUSH_13W": [True, False, True],
            "HERD_TRANSITION": ["BREAKING", "BREAKING", "RECOVERING"],
        }
    )
    assert _policy_mask(rows, policy).tolist() == [True, False, False]


def test_sparsify_enforces_cooldown_and_yearly_cap() -> None:
    dates = pd.to_datetime(
        ["2020-01-03", "2020-02-07", "2020-03-06", "2020-09-04"]
    )
    rows = pd.DataFrame({"signal_date": dates, "value": range(len(dates))})
    selected = _sparsify(rows, maximum_per_year=2, cooldown_weeks=8)
    assert selected["signal_date"].tolist() == [dates[0], dates[2]]


def test_contract_rejects_action_authority(tmp_path: Path) -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    payload["claim_boundary"]["operational_action_ratio"] = 0.05
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ProfitGivebackPolicyV1Error, match="authorize"):
        load_contract(path)
