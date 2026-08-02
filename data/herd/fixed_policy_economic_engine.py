"""Event-level economic comparison for simple fixed five-percent policies."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd


SUPPORTED_POLICIES = {
    "MATCHED_HOLD",
    "TRIM_KEEP_CASH",
    "TRIM_REENTER_21",
    "TRIM_REENTER_63",
    "TRIM_TO_SPY_HORIZON",
}


class FixedPolicyEconomicError(ValueError):
    """Raised when an event cannot be compared without timing ambiguity."""


@dataclass(frozen=True)
class FixedPolicyEconomicResult:
    policy_id: str
    signal_date: str
    observation_session: str
    sale_date: str | None
    terminal_date: str
    reentry_date: str | None
    one_way_cost_bps: int
    event_start_wealth: float
    hold_terminal_wealth: float
    policy_terminal_wealth: float
    normalized_net_terminal_wealth_delta: float
    terminal_ticker_shares: float
    terminal_share_delta: float
    missed_upside_cost: float
    downside_avoided: float
    completed_policy: bool
    average_equity_exposure: float
    one_way_turnover: float
    traded_notional: float
    explicit_cost: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PreparedEconomicPrices:
    """Price frame validated once at the immutable-snapshot boundary."""

    frame: pd.DataFrame
    label: str


def _validated_prices(prices: pd.DataFrame, label: str) -> pd.DataFrame:
    frame = prices.copy()
    if "Date" in frame.columns:
        frame["Date"] = pd.to_datetime(frame["Date"])
        frame = frame.set_index("Date")
    frame.index = pd.to_datetime(frame.index).tz_localize(None).normalize()
    frame = frame.sort_index()
    if not {"Open", "Close"}.issubset(frame.columns):
        raise FixedPolicyEconomicError(f"{label} prices require Open and Close")
    frame = frame[["Open", "Close"]].astype(float)
    if (
        frame.empty
        or frame.index.has_duplicates
        or frame.isna().any().any()
        or not np.isfinite(frame.to_numpy()).all()
        or (frame <= 0).any().any()
    ):
        raise FixedPolicyEconomicError(f"{label} prices are invalid")
    return frame


def prepare_economic_prices(
    prices: pd.DataFrame,
    label: str,
) -> PreparedEconomicPrices:
    """Validate and normalize one price snapshot for repeated event evaluation."""
    return PreparedEconomicPrices(frame=_validated_prices(prices, label), label=label)


def _max_drawdown(wealth: pd.Series) -> float:
    drawdown = wealth / wealth.cummax() - 1.0
    return float(drawdown.min())


def _cost_rates(one_way_cost_bps: int) -> tuple[float, float]:
    if one_way_cost_bps < 0 or one_way_cost_bps >= 10_000:
        raise FixedPolicyEconomicError("one-way cost bps is invalid")
    half = one_way_cost_bps / 20_000
    return half, half


def evaluate_fixed_policy(
    *,
    ticker_prices: pd.DataFrame,
    signal_date: pd.Timestamp | str,
    terminal_date: pd.Timestamp | str,
    policy_id: str,
    one_way_cost_bps: int,
    spy_prices: pd.DataFrame | None = None,
    trim_fraction: float = 0.05,
    horizon_sessions: int = 126,
) -> FixedPolicyEconomicResult:
    """Compare one predeclared policy with an already-held one-share position.

    Information is cut off at the last session close on or before the signal date.
    Every policy trade starts no earlier than the next available session open. The
    terminal date is fixed by the event ledger and never selected from future
    price extrema.
    """
    prepared_ticker = prepare_economic_prices(ticker_prices, "ticker")
    prepared_spy = (
        prepare_economic_prices(spy_prices, "SPY")
        if spy_prices is not None
        else None
    )
    return evaluate_prepared_fixed_policy(
        ticker_prices=prepared_ticker,
        signal_date=signal_date,
        terminal_date=terminal_date,
        policy_id=policy_id,
        one_way_cost_bps=one_way_cost_bps,
        spy_prices=prepared_spy,
        trim_fraction=trim_fraction,
        horizon_sessions=horizon_sessions,
    )


def evaluate_prepared_fixed_policy(
    *,
    ticker_prices: PreparedEconomicPrices,
    signal_date: pd.Timestamp | str,
    terminal_date: pd.Timestamp | str,
    policy_id: str,
    one_way_cost_bps: int,
    spy_prices: PreparedEconomicPrices | None = None,
    trim_fraction: float = 0.05,
    horizon_sessions: int = 126,
) -> FixedPolicyEconomicResult:
    """Evaluate one event using price snapshots validated by the caller once."""
    if policy_id not in SUPPORTED_POLICIES:
        raise FixedPolicyEconomicError(f"unsupported fixed policy: {policy_id}")
    if trim_fraction != 0.05:
        raise FixedPolicyEconomicError("the initial trim must remain five percent")
    if horizon_sessions != 126:
        raise FixedPolicyEconomicError("the event horizon must remain 126 sessions")

    ticker = ticker_prices.frame
    signal = pd.Timestamp(signal_date).tz_localize(None).normalize()
    terminal = pd.Timestamp(terminal_date).tz_localize(None).normalize()
    if terminal not in ticker.index:
        raise FixedPolicyEconomicError("terminal must be an exact session")
    signal_position = int(ticker.index.searchsorted(signal, side="right")) - 1
    if signal_position < 0:
        raise FixedPolicyEconomicError("no observation session exists by signal date")
    terminal_position = ticker.index.get_loc(terminal)
    if not isinstance(terminal_position, int):
        raise FixedPolicyEconomicError("terminal must resolve to one session")
    if terminal_position <= signal_position:
        raise FixedPolicyEconomicError("terminal must follow signal")
    if terminal_position - signal_position != horizon_sessions:
        raise FixedPolicyEconomicError(
            "event does not have the locked 126-session horizon"
        )

    window = ticker.iloc[signal_position : terminal_position + 1]
    observation_session = window.index[0]
    start_wealth = float(window["Close"].iloc[0])
    hold_wealth = window["Close"].copy()
    hold_terminal = float(hold_wealth.iloc[-1])
    fee_rate, slippage_rate = _cost_rates(one_way_cost_bps)

    if policy_id == "MATCHED_HOLD":
        return FixedPolicyEconomicResult(
            policy_id=policy_id,
            signal_date=signal.date().isoformat(),
            observation_session=observation_session.date().isoformat(),
            sale_date=None,
            terminal_date=terminal.date().isoformat(),
            reentry_date=None,
            one_way_cost_bps=one_way_cost_bps,
            event_start_wealth=start_wealth,
            hold_terminal_wealth=hold_terminal,
            policy_terminal_wealth=hold_terminal,
            normalized_net_terminal_wealth_delta=0.0,
            terminal_ticker_shares=1.0,
            terminal_share_delta=0.0,
            missed_upside_cost=0.0,
            downside_avoided=0.0,
            completed_policy=True,
            average_equity_exposure=1.0,
            one_way_turnover=0.0,
            traded_notional=0.0,
            explicit_cost=0.0,
        )

    if len(window) < 2:
        raise FixedPolicyEconomicError("no next session is available for execution")
    sale_date = window.index[1]
    sale_open = float(window.at[sale_date, "Open"])
    sale_execution_price = sale_open * (1 - slippage_rate)
    sold_shares = trim_fraction
    sale_notional = sold_shares * sale_execution_price
    sale_fee = sale_notional * fee_rate
    cash = sale_notional - sale_fee
    ticker_shares = 1.0 - sold_shares
    traded_notional = sale_notional
    explicit_cost = sold_shares * sale_open * slippage_rate + sale_fee
    reentry_date: pd.Timestamp | None = None
    spy_shares = 0.0

    cash_path = pd.Series(0.0, index=window.index)
    ticker_share_path = pd.Series(1.0, index=window.index)
    spy_share_path = pd.Series(0.0, index=window.index)
    cash_path.loc[sale_date:] = cash
    ticker_share_path.loc[sale_date:] = ticker_shares

    if policy_id in {"TRIM_REENTER_21", "TRIM_REENTER_63"}:
        wait = 21 if policy_id.endswith("21") else 63
        reentry_position = 1 + wait
        if reentry_position >= len(window):
            raise FixedPolicyEconomicError(
                f"{policy_id} cannot mature inside the locked event horizon"
            )
        reentry_date = window.index[reentry_position]
        reentry_open = float(window.at[reentry_date, "Open"])
        reentry_execution_price = reentry_open * (1 + slippage_rate)
        buy_notional = cash / (1 + fee_rate)
        buy_fee = buy_notional * fee_rate
        bought_shares = buy_notional / reentry_execution_price
        ticker_shares += bought_shares
        traded_notional += buy_notional
        explicit_cost += bought_shares * reentry_open * slippage_rate + buy_fee
        cash = 0.0
        ticker_share_path.loc[reentry_date:] = ticker_shares
        cash_path.loc[reentry_date:] = 0.0
    elif policy_id == "TRIM_TO_SPY_HORIZON":
        if spy_prices is None:
            raise FixedPolicyEconomicError("SPY prices are required for reallocation")
        spy = spy_prices.frame.reindex(window.index)
        if spy.isna().any().any():
            raise FixedPolicyEconomicError("SPY sessions do not align with ticker")
        spy_open = float(spy.at[sale_date, "Open"])
        spy_execution_price = spy_open * (1 + slippage_rate)
        buy_notional = cash / (1 + fee_rate)
        buy_fee = buy_notional * fee_rate
        spy_shares = buy_notional / spy_execution_price
        traded_notional += buy_notional
        explicit_cost += spy_shares * spy_open * slippage_rate + buy_fee
        cash = 0.0
        spy_share_path.loc[sale_date:] = spy_shares
        cash_path.loc[sale_date:] = 0.0
    elif policy_id != "TRIM_KEEP_CASH":
        raise FixedPolicyEconomicError(f"policy implementation missing: {policy_id}")

    spy_close = pd.Series(0.0, index=window.index)
    if spy_shares > 0:
        spy_close = spy_prices.frame["Close"].reindex(window.index)
    policy_wealth = (
        ticker_share_path * window["Close"]
        + spy_share_path * spy_close
        + cash_path
    )
    equity_value = (
        ticker_share_path * window["Close"] + spy_share_path * spy_close
    )
    exposure = equity_value / policy_wealth
    policy_terminal = float(policy_wealth.iloc[-1])
    normalized_delta = (policy_terminal - hold_terminal) / start_wealth
    downside_avoided = max(
        0.0,
        abs(_max_drawdown(hold_wealth)) - abs(_max_drawdown(policy_wealth)),
    )

    return FixedPolicyEconomicResult(
        policy_id=policy_id,
        signal_date=signal.date().isoformat(),
        observation_session=observation_session.date().isoformat(),
        sale_date=sale_date.date().isoformat(),
        terminal_date=terminal.date().isoformat(),
        reentry_date=(reentry_date.date().isoformat() if reentry_date else None),
        one_way_cost_bps=one_way_cost_bps,
        event_start_wealth=start_wealth,
        hold_terminal_wealth=hold_terminal,
        policy_terminal_wealth=policy_terminal,
        normalized_net_terminal_wealth_delta=float(normalized_delta),
        terminal_ticker_shares=float(ticker_shares),
        terminal_share_delta=float(ticker_shares - 1.0),
        missed_upside_cost=float(max(0.0, -normalized_delta)),
        downside_avoided=float(downside_avoided),
        completed_policy=policy_id != "TRIM_KEEP_CASH",
        average_equity_exposure=float(exposure.mean()),
        one_way_turnover=float(traded_notional / start_wealth),
        traded_notional=float(traded_notional),
        explicit_cost=float(explicit_cost),
    )
