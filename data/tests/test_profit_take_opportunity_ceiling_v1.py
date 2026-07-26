import copy
import json

import pandas as pd
import pytest

from herd.profit_take_opportunity_ceiling_v1 import (
    CONTRACT_PATH,
    OpportunityCeilingError,
    REPORT_PATH,
    _scenario,
    measure_entry,
    validate_contract,
)


def _contract():
    return json.loads(CONTRACT_PATH.read_text())


def test_contract_keeps_s1_sparse_and_non_operational():
    contract = validate_contract(_contract())
    assert contract["event"]["model"] == "HERD_STATE_S1"
    assert contract["event"]["maximum_events_per_ticker_calendar_year"] == 2
    assert contract["decision_boundary"]["operational_action_ratio"] == 0.0


def test_contract_rejects_legacy_selector_or_threshold_change():
    changed = copy.deepcopy(_contract())
    changed["event"]["model"] = "HERD_V6_1"
    with pytest.raises(OpportunityCeilingError):
        validate_contract(changed)
    changed = copy.deepcopy(_contract())
    changed["ceilings"]["constrained_oracle"][
        "minimum_net_sleeve_share_delta_rate"
    ] = 0.01
    with pytest.raises(OpportunityCeilingError):
        validate_contract(changed)


def test_constrained_oracle_requires_three_sessions_and_limits_advance():
    result = _scenario(
        pd.Series([105.0, 96.0, 96.0, 96.0]).to_numpy(),
        100.0,
        fee=0.0,
        slippage=0.0,
        minimum_delta=0.03,
        minimum_run=3,
        maximum_advance=0.10,
    )
    assert result["constrained_available"] is True
    blocked = _scenario(
        pd.Series([112.0, 96.0, 96.0, 96.0]).to_numpy(),
        100.0,
        fee=0.0,
        slippage=0.0,
        minimum_delta=0.03,
        minimum_run=3,
        maximum_advance=0.10,
    )
    assert blocked["constrained_available"] is False


def test_measurement_executes_strictly_after_signal():
    dates = pd.bdate_range("2020-01-01", periods=130)
    prices = pd.DataFrame(
        {
            "Date": dates,
            "AdjustedOpen": [100.0] * 130,
            "AdjustedClose": [100.0] * 130,
        }
    )
    result = measure_entry(prices, dates[0], _contract())
    assert result is not None
    assert result["sale_date"] == dates[1].date().isoformat()


def test_checked_in_ceiling_only_allows_next_label_design():
    report = json.loads(REPORT_PATH.read_text())
    assert report["passed"] is True
    assert report["direction_evidence_admitted"] is False
    assert report["trim_or_reentry_authorized"] is False
    assert report["blind_holdout_access"] is False
    assert report["operational_action_ratio"] == 0.0
