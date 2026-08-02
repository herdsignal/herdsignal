import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.fixed_policy_economic_engine import (
    FixedPolicyEconomicError,
    evaluate_fixed_policy,
)


def _prices(opens, closes=None):
    closes = closes if closes is not None else opens
    return pd.DataFrame(
        {"Open": opens, "Close": closes},
        index=pd.date_range("2025-01-02", periods=len(opens), freq="B"),
    )


def test_matched_hold_has_exactly_zero_incremental_value():
    prices = _prices([100.0] * 130)
    result = evaluate_fixed_policy(
        ticker_prices=prices,
        signal_date=prices.index[0],
        terminal_date=prices.index[126],
        policy_id="MATCHED_HOLD",
        one_way_cost_bps=10,
    )

    assert result.normalized_net_terminal_wealth_delta == 0.0
    assert result.terminal_share_delta == 0.0
    assert result.one_way_turnover == 0.0
    assert result.sale_date is None


def test_trim_executes_only_at_next_session_open_and_keep_cash_is_incomplete():
    prices = _prices([100.0, 120.0] + [120.0] * 128)
    result = evaluate_fixed_policy(
        ticker_prices=prices,
        signal_date=prices.index[0],
        terminal_date=prices.index[126],
        policy_id="TRIM_KEEP_CASH",
        one_way_cost_bps=0,
    )

    assert result.sale_date == prices.index[1].date().isoformat()
    assert result.completed_policy is False
    assert result.terminal_ticker_shares == pytest.approx(0.95)
    assert result.policy_terminal_wealth == pytest.approx(120.0)


def test_fixed_reentry_after_drop_increases_shares_and_terminal_wealth():
    opens = [100.0, 100.0] + [100.0] * 20 + [80.0] + [100.0] * 107
    prices = _prices(opens)
    result = evaluate_fixed_policy(
        ticker_prices=prices,
        signal_date=prices.index[0],
        terminal_date=prices.index[126],
        policy_id="TRIM_REENTER_21",
        one_way_cost_bps=0,
    )

    assert result.reentry_date == prices.index[22].date().isoformat()
    assert result.terminal_share_delta == pytest.approx(0.0125)
    assert result.normalized_net_terminal_wealth_delta > 0
    assert result.completed_policy is True


def test_fixed_reentry_after_rally_records_missed_upside():
    opens = [100.0, 100.0] + [100.0] * 20 + [125.0] + [125.0] * 107
    prices = _prices(opens)
    result = evaluate_fixed_policy(
        ticker_prices=prices,
        signal_date=prices.index[0],
        terminal_date=prices.index[126],
        policy_id="TRIM_REENTER_21",
        one_way_cost_bps=0,
    )

    assert result.terminal_share_delta < 0
    assert result.normalized_net_terminal_wealth_delta < 0
    assert result.missed_upside_cost > 0


def test_spy_reallocation_uses_same_next_open_without_oracle_reentry():
    ticker = _prices([100.0] * 130)
    spy = _prices([100.0, 100.0] + [200.0] * 128)
    result = evaluate_fixed_policy(
        ticker_prices=ticker,
        spy_prices=spy,
        signal_date=ticker.index[0],
        terminal_date=ticker.index[126],
        policy_id="TRIM_TO_SPY_HORIZON",
        one_way_cost_bps=0,
    )

    assert result.sale_date == ticker.index[1].date().isoformat()
    assert result.reentry_date is None
    assert result.terminal_ticker_shares == pytest.approx(0.95)
    assert result.normalized_net_terminal_wealth_delta == pytest.approx(0.05)
    assert result.average_equity_exposure == pytest.approx(1.0)


def test_costs_make_a_flat_completed_cycle_negative():
    prices = _prices([100.0] * 130)
    no_cost = evaluate_fixed_policy(
        ticker_prices=prices,
        signal_date=prices.index[0],
        terminal_date=prices.index[126],
        policy_id="TRIM_REENTER_21",
        one_way_cost_bps=0,
    )
    stressed = evaluate_fixed_policy(
        ticker_prices=prices,
        signal_date=prices.index[0],
        terminal_date=prices.index[126],
        policy_id="TRIM_REENTER_21",
        one_way_cost_bps=50,
    )

    assert no_cost.normalized_net_terminal_wealth_delta == pytest.approx(0.0)
    assert stressed.normalized_net_terminal_wealth_delta < 0
    assert stressed.explicit_cost > 0


def test_policy_fails_when_event_horizon_is_shortened():
    prices = _prices([100.0] * 127)

    with pytest.raises(FixedPolicyEconomicError, match="locked 126-session"):
        evaluate_fixed_policy(
            ticker_prices=prices,
            signal_date=prices.index[0],
            terminal_date=prices.index[40],
            policy_id="TRIM_REENTER_63",
            one_way_cost_bps=10,
        )


def test_non_trading_signal_uses_last_available_close_then_next_open():
    prices = _prices([100.0] * 128)
    friday = prices.index[1]
    saturday = friday + pd.Timedelta(days=1)

    result = evaluate_fixed_policy(
        ticker_prices=prices,
        signal_date=saturday,
        terminal_date=prices.index[127],
        policy_id="TRIM_KEEP_CASH",
        one_way_cost_bps=10,
    )

    assert result.observation_session == friday.date().isoformat()
    assert result.sale_date == prices.index[2].date().isoformat()


def test_non_exact_terminal_session_is_rejected_instead_of_backfilled():
    prices = _prices([100.0] * 130)

    with pytest.raises(FixedPolicyEconomicError, match="exact session"):
        evaluate_fixed_policy(
            ticker_prices=prices,
            signal_date=prices.index[0],
            terminal_date="2025-12-25",
            policy_id="TRIM_KEEP_CASH",
            one_way_cost_bps=10,
        )
