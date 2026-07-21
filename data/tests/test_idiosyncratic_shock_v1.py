import numpy as np
import pandas as pd

from herd.idiosyncratic_shock_v1 import event_features, load_protocol


def _frame(returns):
    dates = pd.bdate_range("2020-01-01", periods=len(returns) + 1)
    close = 100 * np.exp(np.r_[0, np.cumsum(returns)])
    return pd.DataFrame({"Date": dates, "Adj Close": close})


def test_common_market_and_sector_move_is_removed():
    protocol = load_protocol()
    spy_returns = np.linspace(-0.01, 0.01, 150)
    sector_excess = np.sin(np.arange(150)) * 0.002
    stock_returns = 1.2 * spy_returns + 0.7 * sector_excess
    result = event_features(
        _frame(stock_returns), _frame(spy_returns), _frame(spy_returns + sector_excess),
        pd.Timestamp("2021-12-31"), protocol,
    )
    assert abs(result["RESIDUAL_RETURN_20D"]) < 1e-10


def test_protocol_forbids_raw_return_candidate():
    protocol = load_protocol()
    assert "USE_RAW_STOCK_RETURN_AS_CANDIDATE" in protocol["forbidden"]
    assert protocol["research_boundary"]["operational_action_ratio"] == 0.0
