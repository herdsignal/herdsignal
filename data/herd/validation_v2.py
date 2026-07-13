"""HERD Phase A 검증 엔진.

신호일 종가로 판단하고 다음 거래일 시가로 체결한다. 결과 집계, 비용,
walk-forward fold 생성은 전략 규칙과 분리해 같은 조건을 반복 검증한다.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import median
from typing import Callable, Literal

import pandas as pd

from collectors.sector_collector import _multiplier_from_relative_strength


@dataclass(frozen=True)
class ExecutionConfig:
    initial_cash: float = 10_000.0
    fee_rate: float = 0.001
    slippage_bps: float = 10.0
    cooldown_days: int = 20


InvestorScenario = Literal["existing_holder", "new_entry", "monthly_dca", "target_rebalance"]


@dataclass(frozen=True)
class InvestorConfig:
    """투자자 상황별 초기 노출과 정기 자금 흐름 설정."""

    scenario: InvestorScenario = "existing_holder"
    monthly_contribution: float = 500.0
    target_stock_weight: float = 0.7

    def __post_init__(self) -> None:
        if self.monthly_contribution < 0:
            raise ValueError("월 적립액은 0 이상이어야 합니다.")
        if not 0 <= self.target_stock_weight <= 1:
            raise ValueError("목표 주식 비중은 0과 1 사이여야 합니다.")


@dataclass
class Trade:
    signal_date: str
    execution_date: str
    side: str
    ratio: float
    reference_price: float
    execution_price: float
    fee: float
    slippage_cost: float


@dataclass
class ValidationResult:
    ticker: str
    start: str
    end: str
    portfolio_values: list[float]
    trades: list[Trade] = field(default_factory=list)
    initial_value: float = 10_000.0
    performance_values: list[float] = field(default_factory=list)
    contributions: float = 0.0
    investor_scenario: InvestorScenario = "existing_holder"

    @property
    def return_pct(self) -> float:
        values = self.performance_values or self.portfolio_values
        return (values[-1] / self.initial_value - 1) * 100 if values else 0.0

    @property
    def mdd(self) -> float:
        values = self.performance_values or self.portfolio_values
        peak = values[0] if values else 0.0
        worst = 0.0
        for value in values:
            peak = max(peak, value)
            if peak > 0:
                worst = min(worst, (value - peak) / peak * 100)
        return worst

    @property
    def total_cost(self) -> float:
        return sum(trade.fee + trade.slippage_cost for trade in self.trades)


DecisionFn = Callable[[float, pd.Series, float | None, int], tuple[str, float]]


def point_in_time_sector_multiplier(stock_close: pd.Series, sector_close: pd.Series, days: int = 90) -> pd.Series:
    """각 날짜에 당시까지 알려진 90거래일 상대수익률만 사용한다."""
    aligned = pd.concat([stock_close.rename("stock"), sector_close.rename("sector")], axis=1).ffill()
    stock_return = aligned["stock"].pct_change(days) * 100
    sector_return = aligned["sector"].pct_change(days) * 100
    relative = stock_return - sector_return
    return relative.map(lambda value: 1.0 if pd.isna(value) else _multiplier_from_relative_strength(float(value)))


def apply_point_in_time_sector(base_scores: pd.Series, multiplier: pd.Series) -> pd.Series:
    aligned = multiplier.reindex(base_scores.index).ffill().fillna(1.0)
    return (base_scores * aligned).clip(0, 100).round(2)


def normalize_price_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "Date" in out.columns:
        out["Date"] = pd.to_datetime(out["Date"])
        out = out.set_index("Date")
    out.index = pd.to_datetime(out.index)
    if "Open" not in out.columns:
        raise ValueError("다음 거래일 체결 검증에는 Open 가격이 필요합니다.")
    return out.sort_index().dropna(subset=["Open", "Close"])


def run_realistic_strategy(
    ticker: str,
    prices: pd.DataFrame,
    herd: pd.Series,
    trend: pd.DataFrame,
    decide: DecisionFn,
    config: ExecutionConfig = ExecutionConfig(),
    investor: InvestorConfig = InvestorConfig(),
) -> ValidationResult:
    """당일 종가 신호를 다음 거래일 시가에 비용 포함 체결한다."""
    frame = normalize_price_frame(prices)
    herd = herd.reindex(frame.index).ffill()
    trend = trend.reindex(frame.index).ffill()
    cash = config.initial_cash
    first_open = float(frame.iloc[0]["Open"])
    shares = 0.0
    initial_weight = 1.0 if investor.scenario in {"existing_holder", "monthly_dca"} else (
        investor.target_stock_weight if investor.scenario == "target_rebalance" else 0.0
    )
    if initial_weight > 0:
        spend = cash * initial_weight
        initial_fee = spend * config.fee_rate
        shares = (spend - initial_fee) / (first_open * (1 + config.slippage_bps / 10_000))
        cash -= spend
    values: list[float] = []
    performance_values: list[float] = []
    trades: list[Trade] = []
    pending: tuple[str, float, pd.Timestamp, float] | None = None
    previous_score: float | None = None
    previous_action = "HOLD"
    action_days = 0
    last_buy = -config.cooldown_days - 1
    last_sell = -config.cooldown_days - 1
    contributed = 0.0
    performance_index = config.initial_cash
    previous_value = config.initial_cash
    previous_month: tuple[int, int] | None = None

    def trade_to_weight(raw_open: float, target_weight: float) -> None:
        nonlocal cash, shares
        total = cash + shares * raw_open
        target_stock = total * target_weight
        current_stock = shares * raw_open
        if current_stock < target_stock and cash > 0:
            spend = min(cash, target_stock - current_stock)
            fee = spend * config.fee_rate
            execution = raw_open * (1 + config.slippage_bps / 10_000)
            shares += max(0.0, spend - fee) / execution
            cash -= spend
        elif current_stock > target_stock and shares > 0:
            quantity = min(shares, (current_stock - target_stock) / raw_open)
            execution = raw_open * (1 - config.slippage_bps / 10_000)
            gross = quantity * execution
            shares -= quantity
            cash += gross * (1 - config.fee_rate)

    for i, (date, row) in enumerate(frame.iterrows()):
        raw_open = float(row["Open"])
        month = (date.year, date.month)
        external_flow = 0.0
        if pending is not None:
            side, ratio, signal_date, reference = pending
            slip = config.slippage_bps / 10_000
            execution = raw_open * (1 + slip if side == "BUY" else 1 - slip)
            executed = False
            if side == "BUY" and cash > 1:
                spend = cash * ratio
                fee = spend * config.fee_rate
                quantity = max(0.0, spend - fee) / execution
                shares += quantity
                cash -= spend
                slippage_cost = quantity * abs(execution - raw_open)
                executed = quantity > 0
            elif side == "SELL" and shares > 0:
                quantity = shares * ratio
                gross = quantity * execution
                fee = gross * config.fee_rate
                shares -= quantity
                cash += gross - fee
                slippage_cost = quantity * abs(execution - raw_open)
                executed = quantity > 0
            else:
                fee = slippage_cost = 0.0
            if executed:
                trades.append(Trade(str(signal_date.date()), str(date.date()), side, ratio, reference, execution, fee, slippage_cost))
            pending = None

        if previous_month is not None and month != previous_month:
            if investor.scenario == "monthly_dca" and investor.monthly_contribution > 0:
                external_flow = investor.monthly_contribution
                cash += external_flow
                contributed += external_flow
                spend = min(cash, external_flow)
                fee = spend * config.fee_rate
                execution = raw_open * (1 + config.slippage_bps / 10_000)
                shares += max(0.0, spend - fee) / execution
                cash -= spend
            elif investor.scenario == "target_rebalance":
                trade_to_weight(raw_open, investor.target_stock_weight)
        previous_month = month

        close = float(row["Close"])
        value = cash + shares * close
        base = previous_value + external_flow
        if base > 0:
            performance_index *= value / base
        previous_value = value
        values.append(value)
        performance_values.append(performance_index)
        score = herd.get(date)
        if pd.isna(score) or i == len(frame) - 1:
            continue
        score = float(score)
        action, ratio = decide(score, trend.loc[date], previous_score, action_days)
        action_days = action_days + 1 if action == previous_action else 1
        previous_action = action
        previous_score = score
        if action == "BUY" and ratio > 0 and (i - last_buy) > config.cooldown_days:
            pending = (action, ratio, date, close)
            last_buy = i
        elif action == "SELL" and ratio > 0 and (i - last_sell) > config.cooldown_days:
            pending = (action, ratio, date, close)
            last_sell = i

    return ValidationResult(
        ticker, str(frame.index[0].date()), str(frame.index[-1].date()), values, trades,
        config.initial_cash, performance_values, contributed, investor.scenario,
    )


def build_folds(index: pd.DatetimeIndex, mode: str, train_years: int = 4, test_years: int = 1) -> list[dict]:
    """시간 순서를 보존하는 anchored/rolling OOS 구간을 만든다."""
    years = sorted(set(index.year))
    folds: list[dict] = []
    for test_year in years[train_years:]:
        train_start = years[0] if mode == "anchored" else test_year - train_years
        train_end = test_year - 1
        test_end = test_year + test_years - 1
        train_mask = (index.year >= train_start) & (index.year <= train_end)
        test_mask = (index.year >= test_year) & (index.year <= test_end)
        if train_mask.any() and test_mask.any():
            folds.append({"mode": mode, "train_start": train_start, "train_end": train_end, "test_start": test_year, "test_end": test_end})
    return folds


def summarize(rows: list[dict], candidate_prefix: str = "v61", baseline_prefix: str = "fixed") -> dict:
    captures = [r[f"{candidate_prefix}_capture"] for r in rows if r.get(f"{candidate_prefix}_capture") is not None]
    mdd_gains = [r[f"{candidate_prefix}_mdd_improvement"] for r in rows]
    improvements = [r[f"{candidate_prefix}_return"] > r[f"{baseline_prefix}_return"] for r in rows]
    sorted_capture = sorted(captures)
    tail_count = max(1, len(sorted_capture) // 10)
    return {
        "ticker_count": len(rows),
        "capture_median": median(captures) if captures else None,
        "capture_mean": sum(captures) / len(captures) if captures else None,
        "capture_bottom_decile_mean": sum(sorted_capture[:tail_count]) / tail_count if captures else None,
        "mdd_improvement_median": median(mdd_gains) if mdd_gains else None,
        "improvement_rate": sum(improvements) / len(improvements) * 100 if improvements else None,
        "worst_ticker": min(rows, key=lambda row: row[f"{candidate_prefix}_return"])["ticker"] if rows else None,
    }


def write_report(output_dir: Path, metadata: dict, rows: list[dict], folds: list[dict]) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {"metadata": metadata, "summary": summarize(rows), "rows": rows, "walk_forward": folds}
    json_path = output_dir / "validation_v2.json"
    csv_path = output_dir / "validation_v2.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    return json_path, csv_path
