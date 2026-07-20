import pandas as pd

from herd.benchmark_engine import (
    BenchmarkConfig,
    simulate_fractional_actions,
)
from herd.completed_cycle import cycle_metrics, match_completed_cycles


def _prices(values):
    return pd.DataFrame(
        {"Open": values, "Close": values},
        index=pd.date_range("2025-01-01", periods=len(values), freq="B"),
    )


def test_lower_reentry_closes_cycle_with_more_shares():
    prices = _prices([100, 110, 90, 90])
    actions = pd.DataFrame(
        {
            "action": ["SELL", "BUY", "HOLD", "HOLD"],
            "ratio": [0.10, 1.0, 0.0, 0.0],
        },
        index=prices.index,
    )
    result = simulate_fractional_actions(
        "cycle",
        prices,
        actions,
        config=BenchmarkConfig(fee_rate=0.0, slippage_rate=0.0),
    )

    audit = match_completed_cycles(result.trades)
    metrics = cycle_metrics(audit)

    assert metrics["completed_cycle_count"] == 1
    assert metrics["positive_share_cycle_count"] == 1
    assert metrics["completed_cycle_share_delta"] > 0
    assert metrics["open_sale_cash"] == 0


def test_sale_without_reentry_is_not_counted_as_success():
    prices = _prices([100, 110, 90])
    actions = pd.DataFrame(
        {"action": ["SELL", "HOLD", "HOLD"], "ratio": [0.10, 0.0, 0.0]},
        index=prices.index,
    )
    result = simulate_fractional_actions(
        "open-cycle",
        prices,
        actions,
        config=BenchmarkConfig(fee_rate=0.0, slippage_rate=0.0),
    )

    metrics = cycle_metrics(match_completed_cycles(result.trades))

    assert metrics["completed_cycle_count"] == 0
    assert metrics["open_sale_count"] == 1
    assert metrics["open_sale_cash"] > 0


def test_higher_reentry_closes_cycle_with_fewer_shares():
    prices = _prices([100, 90, 120, 120])
    actions = pd.DataFrame(
        {
            "action": ["SELL", "BUY", "HOLD", "HOLD"],
            "ratio": [0.10, 1.0, 0.0, 0.0],
        },
        index=prices.index,
    )
    result = simulate_fractional_actions(
        "bad-cycle",
        prices,
        actions,
        config=BenchmarkConfig(fee_rate=0.0, slippage_rate=0.0),
    )

    metrics = cycle_metrics(match_completed_cycles(result.trades))

    assert metrics["completed_cycle_count"] == 1
    assert metrics["positive_share_cycle_count"] == 0
    assert metrics["completed_cycle_share_delta"] < 0


def test_initial_buy_is_ignored_because_it_is_not_reentry():
    prices = _prices([100, 100])
    actions = pd.DataFrame(
        {"action": ["HOLD", "HOLD"], "ratio": [0.0, 0.0]},
        index=prices.index,
    )
    result = simulate_fractional_actions(
        "hold",
        prices,
        actions,
        config=BenchmarkConfig(fee_rate=0.0, slippage_rate=0.0),
    )

    audit = match_completed_cycles(result.trades)

    assert audit.completed_cycles == ()
    assert audit.unmatched_buy_cost == 0
