from datetime import date, timedelta

import pandas as pd
import pytest

from herd.benchmark_engine import (
    BenchmarkConfig,
    simulate_fractional_actions,
)
from herd.completed_cycle import (
    ExplicitCycleEvent,
    cycle_metrics,
    match_completed_cycles,
    replay_matched_cash_cycles,
)


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


def _cycle_event(
    event_id,
    event_type,
    session,
    *,
    cycle_id="NVDA-1",
    ticker="NVDA",
    shares=1.0,
    notional=100.0,
    fee=0.0,
):
    return ExplicitCycleEvent(
        event_id=event_id,
        cycle_id=cycle_id,
        ticker=ticker,
        session_index=session,
        occurred_on=date(2026, 1, 1) + timedelta(days=session),
        event_type=event_type,
        shares=shares,
        notional=notional,
        fee=fee,
    )


def test_explicit_cycle_completes_only_with_matched_sale_cash():
    audit = replay_matched_cash_cycles(
        [
            _cycle_event("trim", "TRIM", 0, shares=1.0, notional=100.0),
            _cycle_event("reentry", "REENTRY", 2, shares=1.25, notional=100.0),
        ],
        as_of_session_index=2,
    )

    cycle = audit.cycles[0]
    assert cycle.status == "COMPLETED"
    assert cycle.share_delta == pytest.approx(0.25)
    assert audit.completed_cycle_count == 1
    assert audit.reserved_cash == 0


def test_explicit_cycle_preserves_partial_reentry_and_reserved_cash():
    audit = replay_matched_cash_cycles(
        [
            _cycle_event("trim", "TRIM", 0, notional=100.0),
            _cycle_event("partial", "REENTRY", 2, shares=0.5, notional=40.0),
        ],
        as_of_session_index=10,
    )

    cycle = audit.cycles[0]
    assert cycle.status == "PARTIAL_REENTRY"
    assert cycle.remaining_cash == pytest.approx(60.0)
    assert cycle.share_delta is None
    assert audit.reserved_cash == pytest.approx(60.0)


def test_explicit_cycle_expires_without_counting_success():
    audit = replay_matched_cash_cycles(
        [_cycle_event("trim", "TRIM", 0, notional=100.0)],
        as_of_session_index=127,
    )

    assert audit.cycles[0].status == "EXPIRED"
    assert audit.cycles[0].share_delta is None
    assert audit.completed_cycle_count == 0
    assert audit.expired_cycle_count == 1
    assert audit.expired_cash == pytest.approx(100.0)


@pytest.mark.parametrize(
    "events,error",
    [
        (
            [_cycle_event("buy", "REENTRY", 2)],
            "no matched trim",
        ),
        (
            [
                _cycle_event("trim", "TRIM", 0),
                _cycle_event("buy", "REENTRY", 2, ticker="TSLA"),
            ],
            "ticker must match",
        ),
        (
            [
                _cycle_event("trim", "TRIM", 0, notional=100.0),
                _cycle_event("buy", "REENTRY", 2, notional=101.0),
            ],
            "external or unmatched cash",
        ),
        (
            [
                _cycle_event("trim", "TRIM", 0),
                _cycle_event("buy", "REENTRY", 127),
            ],
            "after cycle expiry",
        ),
    ],
)
def test_explicit_cycle_rejects_unmatched_or_invalid_reentry(events, error):
    with pytest.raises(ValueError, match=error):
        replay_matched_cash_cycles(events, as_of_session_index=127)
