"""HERD 전략과 Buy & Hold를 같은 조건으로 비교하는 공통 엔진."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt

import numpy as np
import pandas as pd

TRADING_DAYS = 252


@dataclass(frozen=True)
class BenchmarkConfig:
    initial_cash: float = 10_000.0
    fee_rate: float = 0.001
    slippage_rate: float = 0.0005
    annual_cash_yield: float = 0.0
    execution_lag: int = 1
    initial_weight: float = 1.0

    def __post_init__(self) -> None:
        if self.initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        if not 0 <= self.fee_rate < 1:
            raise ValueError("fee_rate must be between 0 and 1")
        if not 0 <= self.slippage_rate < 1:
            raise ValueError("slippage_rate must be between 0 and 1")
        if self.execution_lag < 1:
            raise ValueError("execution_lag must be at least 1 to prevent look-ahead")
        if not 0 <= self.initial_weight <= 1:
            raise ValueError("initial_weight must be between 0 and 1")


@dataclass
class Trade:
    signal_date: pd.Timestamp | None
    execution_date: pd.Timestamp
    side: str
    shares: float
    reference_price: float
    execution_price: float
    notional: float
    fee: float
    target_weight: float


@dataclass
class SimulationResult:
    name: str
    equity: pd.Series
    daily_returns: pd.Series
    exposure: pd.Series
    cash: pd.Series
    shares: pd.Series
    external_flows: pd.Series
    config: BenchmarkConfig
    trades: list[Trade] = field(default_factory=list)
    contributed_capital: float = 0.0


def _price_frame(prices: pd.DataFrame) -> pd.DataFrame:
    frame = prices.copy()
    if "Date" in frame.columns:
        frame["Date"] = pd.to_datetime(frame["Date"])
        frame = frame.set_index("Date")
    frame.index = pd.to_datetime(frame.index)
    frame = frame.sort_index()
    required = {"Open", "Close"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"missing price columns: {sorted(missing)}")
    frame = frame[["Open", "Close"]].astype(float).dropna()
    if frame.empty or (frame <= 0).any().any():
        raise ValueError("prices must contain positive Open and Close values")
    if frame.index.has_duplicates:
        raise ValueError("price dates must be unique")
    return frame


def _series_on_index(
    values: pd.Series | None,
    index: pd.DatetimeIndex,
    *,
    default: float,
) -> pd.Series:
    if values is None:
        return pd.Series(default, index=index, dtype=float)
    series = values.copy()
    series.index = pd.to_datetime(series.index)
    return series.astype(float).reindex(index)


def _execute_target(
    *,
    cash: float,
    shares: float,
    open_price: float,
    target_weight: float,
    config: BenchmarkConfig,
    signal_date: pd.Timestamp | None,
    execution_date: pd.Timestamp,
) -> tuple[float, float, Trade | None]:
    target = float(np.clip(target_weight, 0.0, 1.0))
    equity_at_open = cash + shares * open_price
    current_notional = shares * open_price
    desired_notional = equity_at_open * target
    delta = desired_notional - current_notional
    if abs(delta) < 1e-8:
        return cash, shares, None

    if delta > 0:
        execution_price = open_price * (1 + config.slippage_rate)
        affordable = cash / (execution_price * (1 + config.fee_rate))
        trade_shares = min(delta / execution_price, affordable)
        if trade_shares <= 0:
            return cash, shares, None
        notional = trade_shares * execution_price
        fee = notional * config.fee_rate
        cash -= notional + fee
        shares += trade_shares
        side = "BUY"
    else:
        execution_price = open_price * (1 - config.slippage_rate)
        trade_shares = min(abs(delta) / execution_price, shares)
        if trade_shares <= 0:
            return cash, shares, None
        notional = trade_shares * execution_price
        fee = notional * config.fee_rate
        cash += notional - fee
        shares -= trade_shares
        side = "SELL"

    trade = Trade(
        signal_date=signal_date,
        execution_date=execution_date,
        side=side,
        shares=float(trade_shares),
        reference_price=float(open_price),
        execution_price=float(execution_price),
        notional=float(notional),
        fee=float(fee),
        target_weight=target,
    )
    return cash, shares, trade


def simulate(
    name: str,
    prices: pd.DataFrame,
    target_weights: pd.Series,
    *,
    config: BenchmarkConfig | None = None,
    contributions: pd.Series | None = None,
) -> SimulationResult:
    """목표 비중 신호를 최소 1거래일 뒤 시가에 실행한다."""
    cfg = config or BenchmarkConfig()
    frame = _price_frame(prices)
    targets = _series_on_index(target_weights, frame.index, default=float("nan"))
    flows = _series_on_index(contributions, frame.index, default=0.0).fillna(0.0)
    if (flows < 0).any():
        raise ValueError("contributions cannot be negative")

    cash = cfg.initial_cash
    shares = 0.0
    trades: list[Trade] = []
    equity_values: list[float] = []
    return_values: list[float] = []
    exposure_values: list[float] = []
    cash_values: list[float] = []
    share_values: list[float] = []
    previous_equity = cfg.initial_cash
    daily_cash_rate = (1 + cfg.annual_cash_yield) ** (1 / TRADING_DAYS) - 1

    # 모든 전략의 공통 초기 상태. 첫날 시가에서만 예외적으로 실행한다.
    cash, shares, initial_trade = _execute_target(
        cash=cash,
        shares=shares,
        open_price=float(frame["Open"].iloc[0]),
        target_weight=cfg.initial_weight,
        config=cfg,
        signal_date=None,
        execution_date=frame.index[0],
    )
    if initial_trade:
        trades.append(initial_trade)

    for position, (date, row) in enumerate(frame.iterrows()):
        contribution = float(flows.loc[date])
        cash += contribution

        signal_position = position - cfg.execution_lag
        if signal_position >= 0:
            signal_date = frame.index[signal_position]
            target = targets.iloc[signal_position]
            if pd.notna(target):
                cash, shares, trade = _execute_target(
                    cash=cash,
                    shares=shares,
                    open_price=float(row["Open"]),
                    target_weight=float(target),
                    config=cfg,
                    signal_date=signal_date,
                    execution_date=date,
                )
                if trade:
                    trades.append(trade)

        cash *= 1 + daily_cash_rate
        equity = cash + shares * float(row["Close"])
        exposure = shares * float(row["Close"]) / equity if equity > 0 else 0.0
        daily_return = (equity - contribution) / previous_equity - 1.0

        equity_values.append(equity)
        return_values.append(daily_return)
        exposure_values.append(exposure)
        cash_values.append(cash)
        share_values.append(shares)
        previous_equity = equity

    index = frame.index
    return SimulationResult(
        name=name,
        equity=pd.Series(equity_values, index=index, name=name),
        daily_returns=pd.Series(return_values, index=index, name=name),
        exposure=pd.Series(exposure_values, index=index, name=name),
        cash=pd.Series(cash_values, index=index, name=name),
        shares=pd.Series(share_values, index=index, name=name),
        external_flows=flows,
        config=cfg,
        trades=trades,
        contributed_capital=cfg.initial_cash + float(flows.sum()),
    )


def simulate_fractional_actions(
    name: str,
    prices: pd.DataFrame,
    actions: pd.DataFrame,
    *,
    config: BenchmarkConfig | None = None,
) -> SimulationResult:
    """BUY는 현금, SELL은 보유 주식의 지정 비율만큼 다음 시가에 실행한다."""
    cfg = config or BenchmarkConfig()
    frame = _price_frame(prices)
    action_frame = actions.copy()
    action_frame.index = pd.to_datetime(action_frame.index)
    action_frame = action_frame.reindex(frame.index)
    if not {"action", "ratio"}.issubset(action_frame.columns):
        raise ValueError("actions must contain action and ratio columns")

    cash = cfg.initial_cash
    shares = 0.0
    trades: list[Trade] = []
    equity_values: list[float] = []
    returns: list[float] = []
    exposures: list[float] = []
    cash_values: list[float] = []
    share_values: list[float] = []
    previous_equity = cfg.initial_cash
    daily_cash_rate = (1 + cfg.annual_cash_yield) ** (1 / TRADING_DAYS) - 1

    cash, shares, initial_trade = _execute_target(
        cash=cash, shares=shares, open_price=float(frame["Open"].iloc[0]),
        target_weight=cfg.initial_weight, config=cfg, signal_date=None,
        execution_date=frame.index[0],
    )
    if initial_trade:
        trades.append(initial_trade)

    for position, (date, row) in enumerate(frame.iterrows()):
        signal_position = position - cfg.execution_lag
        if signal_position >= 0:
            signal_date = frame.index[signal_position]
            signal = action_frame.iloc[signal_position]
            action = str(signal.get("action", "HOLD")).upper()
            ratio_value = signal.get("ratio", 0.0)
            ratio = float(ratio_value) if pd.notna(ratio_value) else 0.0
            if not 0 <= ratio <= 1:
                raise ValueError("action ratio must be between 0 and 1")

            open_price = float(row["Open"])
            if action == "BUY" and ratio > 0 and cash > 0:
                execution_price = open_price * (1 + cfg.slippage_rate)
                budget = cash * ratio
                notional = budget / (1 + cfg.fee_rate)
                trade_shares = notional / execution_price
                fee = notional * cfg.fee_rate
                cash -= notional + fee
                shares += trade_shares
                target = shares * open_price / (cash + shares * open_price)
                trades.append(Trade(
                    signal_date=signal_date,
                    execution_date=date,
                    side=action,
                    shares=trade_shares,
                    reference_price=open_price,
                    execution_price=execution_price,
                    notional=notional,
                    fee=fee,
                    target_weight=target,
                ))
            elif action == "SELL" and ratio > 0 and shares > 0:
                execution_price = open_price * (1 - cfg.slippage_rate)
                trade_shares = shares * ratio
                notional = trade_shares * execution_price
                fee = notional * cfg.fee_rate
                cash += notional - fee
                shares -= trade_shares
                target = shares * open_price / (cash + shares * open_price)
                trades.append(Trade(
                    signal_date=signal_date,
                    execution_date=date,
                    side=action,
                    shares=trade_shares,
                    reference_price=open_price,
                    execution_price=execution_price,
                    notional=notional,
                    fee=fee,
                    target_weight=target,
                ))
            elif action not in {"BUY", "SELL", "HOLD", "NAN"}:
                raise ValueError(f"unsupported action: {action}")

        cash *= 1 + daily_cash_rate
        equity = cash + shares * float(row["Close"])
        equity_values.append(equity)
        returns.append(equity / previous_equity - 1.0)
        exposures.append(shares * float(row["Close"]) / equity if equity > 0 else 0.0)
        cash_values.append(cash)
        share_values.append(shares)
        previous_equity = equity

    index = frame.index
    return SimulationResult(
        name=name,
        equity=pd.Series(equity_values, index=index, name=name),
        daily_returns=pd.Series(returns, index=index, name=name),
        exposure=pd.Series(exposures, index=index, name=name),
        cash=pd.Series(cash_values, index=index, name=name),
        shares=pd.Series(share_values, index=index, name=name),
        external_flows=pd.Series(0.0, index=index),
        config=cfg,
        trades=trades,
        contributed_capital=cfg.initial_cash,
    )


def buy_and_hold(
    prices: pd.DataFrame,
    *,
    config: BenchmarkConfig | None = None,
    contributions: pd.Series | None = None,
) -> SimulationResult:
    frame = _price_frame(prices)
    targets = pd.Series(1.0, index=frame.index)
    return simulate("Buy & Hold", frame, targets, config=config, contributions=contributions)


def _max_drawdown(returns: pd.Series) -> float:
    wealth = (1 + returns.fillna(0.0)).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    return float(drawdown.min())


def _validate_comparable(
    result: SimulationResult,
    benchmark: SimulationResult,
) -> None:
    if not result.equity.index.equals(benchmark.equity.index):
        raise ValueError("strategy and benchmark must use identical dates")
    if result.config != benchmark.config:
        raise ValueError("strategy and benchmark must use identical execution costs")
    if result.contributed_capital != benchmark.contributed_capital:
        raise ValueError("strategy and benchmark must use identical capital")
    if not result.external_flows.equals(benchmark.external_flows):
        raise ValueError("strategy and benchmark must use identical external flows")


def performance_metrics(
    result: SimulationResult,
    benchmark: SimulationResult | None = None,
    *,
    risk_free_rate: float = 0.0,
) -> dict[str, float | int | None]:
    returns = result.daily_returns.dropna()
    observations = len(returns)
    years = observations / TRADING_DAYS
    total_return = float((1 + returns).prod() - 1) if observations else 0.0
    cagr = float((1 + total_return) ** (1 / years) - 1) if years > 0 and total_return > -1 else None
    mdd = _max_drawdown(returns) if observations else 0.0
    downside = returns[returns < 0]
    downside_deviation = float(downside.std(ddof=0) * sqrt(TRADING_DAYS)) if len(downside) else 0.0
    annual_return = float(returns.mean() * TRADING_DAYS) if observations else 0.0
    sortino = (
        (annual_return - risk_free_rate) / downside_deviation
        if downside_deviation > 0 else None
    )
    calmar = cagr / abs(mdd) if cagr is not None and mdd < 0 else None
    average_equity = float(result.equity.mean()) if len(result.equity) else 0.0
    turnover = (
        sum(trade.notional for trade in result.trades) / average_equity
        if average_equity > 0 else 0.0
    )
    total_fees = sum(trade.fee for trade in result.trades)
    slippage_cost = sum(
        abs(trade.execution_price - trade.reference_price) * trade.shares
        for trade in result.trades
    )

    metrics: dict[str, float | int | None] = {
        "observations": observations,
        "years": years,
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": mdd,
        "downside_deviation": downside_deviation,
        "sortino": sortino,
        "calmar": calmar,
        "trade_count": len(result.trades),
        "turnover": turnover,
        "average_exposure": float(result.exposure.mean()),
        "average_cash_ratio": float((result.cash / result.equity).mean()),
        "contributed_capital": result.contributed_capital,
        "final_equity": float(result.equity.iloc[-1]),
        "final_cash": float(result.cash.iloc[-1]),
        "terminal_shares": float(result.shares.iloc[-1]),
        "total_fees": float(total_fees),
        "estimated_slippage_cost": float(slippage_cost),
        "upside_capture": None,
        "downside_capture": None,
        "excess_cagr": None,
        "terminal_wealth_delta": None,
        "terminal_share_delta": None,
    }

    if benchmark is not None:
        _validate_comparable(result, benchmark)
        aligned = pd.concat(
            [returns.rename("strategy"), benchmark.daily_returns.rename("benchmark")],
            axis=1,
        ).dropna()
        positive = aligned["benchmark"] > 0
        negative = aligned["benchmark"] < 0
        metrics["upside_capture"] = (
            float(aligned.loc[positive, "strategy"].mean() / aligned.loc[positive, "benchmark"].mean())
            if positive.any() else None
        )
        metrics["downside_capture"] = (
            float(aligned.loc[negative, "strategy"].mean() / aligned.loc[negative, "benchmark"].mean())
            if negative.any() else None
        )
        benchmark_metrics = performance_metrics(benchmark)
        benchmark_cagr = benchmark_metrics["cagr"]
        metrics["excess_cagr"] = (
            cagr - float(benchmark_cagr)
            if cagr is not None and benchmark_cagr is not None else None
        )
        metrics["terminal_wealth_delta"] = (
            float(result.equity.iloc[-1] - benchmark.equity.iloc[-1])
        )
        metrics["terminal_share_delta"] = (
            float(result.shares.iloc[-1] - benchmark.shares.iloc[-1])
        )

    return metrics
