import pandas as pd
import pytest

from herd.indicator_inventory import _expanding_percentile
from herd.v61_baseline_diagnostic_v1 import (
    classify_action_outcome,
    equity_universe,
    forward_path,
)


def test_equity_universe_excludes_market_context_etfs():
    tickers = equity_universe()
    assert len(tickers) == 51
    assert not {"SPY", "QQQ", "DIA", "IWM"}.intersection(tickers)


def test_forward_path_uses_only_sessions_after_signal():
    dates = pd.bdate_range("2020-01-01", periods=140)
    close = pd.Series(range(100, 240), index=dates, dtype=float)
    path = forward_path(close, dates[0])
    assert path is not None
    assert path["terminal_return_1m"] == pytest.approx(21 / 100)
    assert path["terminal_return_6m"] == pytest.approx(126 / 100)


def test_forward_path_fails_closed_without_full_six_month_horizon():
    dates = pd.bdate_range("2020-01-01", periods=126)
    close = pd.Series(range(100, 226), index=dates, dtype=float)
    assert forward_path(close, dates[0]) is None


def test_sell_and_buy_outcomes_have_different_targets():
    path = {"mae_6m": -0.08, "terminal_return_6m": 0.12}
    sell = classify_action_outcome("SELL", path)
    buy = classify_action_outcome("BUY", path)
    assert sell["helpful_6m"] is True
    assert sell["foregone_terminal_upside_6m"] == pytest.approx(0.12)
    assert buy["helpful_6m"] is True
    assert buy["forward_drawdown_6m"] == pytest.approx(-0.08)


def test_unsupported_action_is_rejected():
    with pytest.raises(ValueError):
        classify_action_outcome("HOLD", {"mae_6m": 0, "terminal_return_6m": 0})


def test_fast_expanding_percentile_matches_pandas_rank_contract():
    values = pd.Series([3.0, float("nan"), 1.0, 3.0, 2.0, 3.0])
    expected = values.expanding(min_periods=2).apply(
        lambda window: pd.Series(window).rank(pct=True).iloc[-1] * 100.0,
        raw=False,
    )
    pd.testing.assert_series_equal(_expanding_percentile(values, 2), expected)
