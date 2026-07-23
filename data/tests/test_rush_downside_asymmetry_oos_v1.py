import numpy as np
import pandas as pd

from herd.rush_downside_asymmetry_oos_v1 import (
    apply_sparse_transition_policy,
    asymmetry_score_at,
)
from herd.rush_downside_asymmetry_universe_v1 import load_protocol


def test_downside_residual_expansion_raises_score():
    protocol = load_protocol()
    dates = pd.bdate_range("2020-01-01", periods=190)
    spy = np.sin(np.arange(190)) * 0.001
    sector_excess = np.cos(np.arange(190)) * 0.001
    stock = 0.8 * spy + 0.4 * sector_excess
    stock[-20:] += np.where(np.arange(20) % 2 == 0, -0.02, 0.002)
    factors = pd.DataFrame(
        {"stock": stock, "spy": spy, "sector_excess": sector_excess}, index=dates
    )
    score = asymmetry_score_at(factors, dates[-1], protocol)
    assert score is not None
    assert score > protocol["observation"]["threshold"]


def test_score_contract_rejects_a_gap_different_from_current_window():
    protocol = load_protocol()
    protocol["observation"]["estimation_gap_sessions"] = 21
    dates = pd.bdate_range("2020-01-01", periods=190)
    factors = pd.DataFrame(
        {"stock": np.zeros(190), "spy": np.zeros(190), "sector_excess": np.zeros(190)},
        index=dates,
    )
    try:
        asymmetry_score_at(factors, dates[-1], protocol)
    except ValueError as error:
        assert "gap" in str(error)
    else:
        raise AssertionError("mismatched estimation gap must fail closed")


def test_sparse_policy_enforces_cooldown_and_annual_cap():
    protocol = load_protocol()
    threshold = protocol["observation"]["threshold"]
    panel = pd.DataFrame([
        {"ticker": "A", "last_observed_session": "2020-01-01", "session_position": 100, "downside_asymmetry_score": threshold + 1, "previous_score_5d": 0},
        {"ticker": "A", "last_observed_session": "2020-03-01", "session_position": 150, "downside_asymmetry_score": threshold + 1, "previous_score_5d": 0},
        {"ticker": "A", "last_observed_session": "2020-10-01", "session_position": 300, "downside_asymmetry_score": threshold + 1, "previous_score_5d": 0},
        {"ticker": "A", "last_observed_session": "2020-12-01", "session_position": 450, "downside_asymmetry_score": threshold + 1, "previous_score_5d": 0},
    ])
    result = apply_sparse_transition_policy(panel, protocol)
    assert result["transition_triggered"].tolist() == [True, False, True, False]
