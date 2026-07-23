"""외부 저축과 모델 성과를 분리하는 HERD vNext 현금흐름 비교 계약."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from herd.benchmark_engine import (
    BenchmarkConfig,
    SimulationResult,
    buy_and_hold,
    performance_metrics,
    simulate,
)


CONTRACT_PATH = Path(__file__).with_suffix(".json")
CONTRACT_VERSION = "HERD_PERSONAL_CASHFLOW_BENCHMARK_V1"
ScenarioId = Literal[
    "NO_FUTURE_CONTRIBUTIONS",
    "FIXED_MONTHLY_NEW_CASH",
    "OBSERVED_PERSONAL_CASHFLOWS",
]
REQUIRED_SCENARIOS = [
    "NO_FUTURE_CONTRIBUTIONS",
    "FIXED_MONTHLY_NEW_CASH",
    "OBSERVED_PERSONAL_CASHFLOWS",
]


class CashflowBenchmarkError(ValueError):
    """현금흐름 비교의 공정성 계약이 깨졌을 때 발생한다."""


@dataclass(frozen=True)
class CashflowAttribution:
    initial_capital: float
    net_external_contributions: float
    final_equity: float
    investment_gain: float
    terminal_shares: float
    time_weighted_return: float
    annualized_time_weighted_return: float | None
    annualized_money_weighted_return: float | None


@dataclass(frozen=True)
class MatchedCashflowComparison:
    scenario: ScenarioId
    strategy: SimulationResult
    benchmark: SimulationResult
    strategy_attribution: CashflowAttribution
    benchmark_attribution: CashflowAttribution
    comparison_metrics: dict[str, float | int | None]


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_contract(contract: dict[str, Any]) -> dict[str, Any]:
    if (
        contract.get("contract_version") != CONTRACT_VERSION
        or contract.get("status") != "LOCKED_BEFORE_VNEXT_ACTION_RESULTS"
    ):
        raise CashflowBenchmarkError("cashflow contract is not locked")

    scenario_ids = [
        item.get("id") for item in contract.get("cashflow_scenarios", [])
    ]
    if scenario_ids != REQUIRED_SCENARIOS:
        raise CashflowBenchmarkError("cashflow scenarios changed")

    comparison = contract.get("comparison_rules", {})
    required_true = {
        "same_initial_capital",
        "same_external_cashflows",
        "same_price_and_dividend_series",
        "same_execution_lag_and_costs",
        "external_cashflow_may_not_depend_on_future_price",
        "contribution_is_not_return",
        "earned_income_contribution_is_not_lump_sum_dca",
    }
    if any(comparison.get(key) is not True for key in required_true):
        raise CashflowBenchmarkError("matched comparison rule was weakened")
    if comparison.get("withdrawals_supported") is not False:
        raise CashflowBenchmarkError("withdrawals require a separate execution policy")

    returns = contract.get("return_contract", {})
    if (
        returns.get("model_skill_metric") != "TIME_WEIGHTED_RETURN"
        or returns.get("investor_experience_metric")
        != "MONEY_WEIGHTED_RETURN_XIRR"
        or returns.get("periods_shorter_than_one_year_are_not_annualized") is not True
    ):
        raise CashflowBenchmarkError("return attribution contract changed")

    promotion = contract.get("promotion_boundary", {})
    if (
        promotion.get("cashflow_adjusted_outperformance_required") is not True
        or promotion.get("single_cashflow_scenario_is_insufficient") is not True
        or promotion.get("operational_action_authority") is not False
    ):
        raise CashflowBenchmarkError("cashflow diagnostics cannot authorize actions")

    return {
        "report_version": "HERD_PERSONAL_CASHFLOW_BENCHMARK_AUDIT_V1",
        "status": "CASHFLOW_BENCHMARK_CONTRACT_VERIFIED",
        "scenario_ids": scenario_ids,
        "model_skill_metric": "TIME_WEIGHTED_RETURN",
        "investor_experience_metric": "MONEY_WEIGHTED_RETURN_XIRR",
        "matched_external_cashflows_required": True,
        "operational_action_authority": False,
    }


def _validated_index(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    result = pd.DatetimeIndex(pd.to_datetime(index)).sort_values()
    if result.empty or result.has_duplicates:
        raise CashflowBenchmarkError("price index must be non-empty and unique")
    return result


def build_external_cashflows(
    index: pd.DatetimeIndex,
    scenario: ScenarioId,
    *,
    monthly_amount: float = 0.0,
    observed: pd.Series | None = None,
) -> pd.Series:
    """가격과 무관하게 사전에 정한 외부 입금 시계열을 만든다."""
    dates = _validated_index(index)
    flows = pd.Series(0.0, index=dates, name="external_cashflow")

    if scenario == "NO_FUTURE_CONTRIBUTIONS":
        if monthly_amount != 0 or observed is not None:
            raise CashflowBenchmarkError("no-contribution scenario received cashflows")
        return flows

    if scenario == "FIXED_MONTHLY_NEW_CASH":
        if monthly_amount <= 0 or observed is not None:
            raise CashflowBenchmarkError(
                "fixed-monthly scenario requires a positive monthly amount only"
            )
        months = dates.to_period("M")
        first_positions = np.flatnonzero(months != np.roll(months, 1))
        # 초기 자본과 중복되지 않도록 시작 월의 첫 거래일은 제외한다.
        for position in first_positions[1:]:
            flows.iloc[int(position)] = float(monthly_amount)
        return flows

    if scenario == "OBSERVED_PERSONAL_CASHFLOWS":
        if observed is None or monthly_amount != 0:
            raise CashflowBenchmarkError(
                "observed scenario requires an observed series only"
            )
        supplied = observed.astype(float).copy()
        supplied.index = pd.to_datetime(supplied.index)
        if supplied.index.has_duplicates:
            raise CashflowBenchmarkError("observed cashflow dates must be unique")
        outside = supplied.index.difference(dates)
        if len(outside):
            raise CashflowBenchmarkError("observed cashflow is outside price dates")
        if (
            supplied.isna().any()
            or not np.isfinite(supplied.to_numpy()).all()
            or (supplied < 0).any()
        ):
            raise CashflowBenchmarkError(
                "observed contributions must be finite and non-negative"
            )
        return supplied.reindex(dates, fill_value=0.0).rename("external_cashflow")

    raise CashflowBenchmarkError(f"unsupported cashflow scenario: {scenario}")


def _xnpv(rate: float, dates: pd.DatetimeIndex, amounts: list[float]) -> float:
    origin = dates[0]
    years = (dates - origin).days.astype(float) / 365.25
    return float(
        sum(amount / ((1.0 + rate) ** year) for amount, year in zip(amounts, years))
    )


def annualized_money_weighted_return(result: SimulationResult) -> float | None:
    """통상적인 음수 입금·양수 종가 현금흐름의 XIRR을 계산한다."""
    dates = result.equity.index
    if len(dates) < 2 or (dates[-1] - dates[0]).days < 365:
        return None

    cashflow_dates = [dates[0]]
    amounts = [-float(result.config.initial_cash)]
    for date, amount in result.external_flows.items():
        if amount > 0:
            cashflow_dates.append(pd.Timestamp(date))
            amounts.append(-float(amount))
    cashflow_dates.append(dates[-1])
    amounts.append(float(result.equity.iloc[-1]))

    ordered = sorted(zip(cashflow_dates, amounts), key=lambda item: item[0])
    xirr_dates = pd.DatetimeIndex([item[0] for item in ordered])
    xirr_amounts = [item[1] for item in ordered]
    if not any(value < 0 for value in xirr_amounts) or not any(
        value > 0 for value in xirr_amounts
    ):
        return None

    low = -0.999999
    high = 1.0
    low_value = _xnpv(low, xirr_dates, xirr_amounts)
    high_value = _xnpv(high, xirr_dates, xirr_amounts)
    while low_value * high_value > 0 and high < 1_000_000:
        high *= 2
        high_value = _xnpv(high, xirr_dates, xirr_amounts)
    if low_value * high_value > 0:
        return None

    for _ in range(200):
        middle = (low + high) / 2
        value = _xnpv(middle, xirr_dates, xirr_amounts)
        if abs(value) < 1e-10:
            return float(middle)
        if low_value * value <= 0:
            high = middle
        else:
            low = middle
            low_value = value
    return float((low + high) / 2)


def attribute_result(result: SimulationResult) -> CashflowAttribution:
    returns = result.daily_returns.fillna(0.0)
    twr = float((1.0 + returns).prod() - 1.0)
    days = int((result.equity.index[-1] - result.equity.index[0]).days)
    annualized_twr = (
        float((1.0 + twr) ** (365.25 / days) - 1.0)
        if days >= 365 and twr > -1
        else None
    )
    initial = float(result.config.initial_cash)
    contributions = float(result.external_flows.sum())
    final_equity = float(result.equity.iloc[-1])
    return CashflowAttribution(
        initial_capital=initial,
        net_external_contributions=contributions,
        final_equity=final_equity,
        investment_gain=final_equity - initial - contributions,
        terminal_shares=float(result.shares.iloc[-1]),
        time_weighted_return=twr,
        annualized_time_weighted_return=annualized_twr,
        annualized_money_weighted_return=annualized_money_weighted_return(result),
    )


def compare_with_matched_buy_and_hold(
    scenario: ScenarioId,
    prices: pd.DataFrame,
    target_weights: pd.Series,
    external_cashflows: pd.Series,
    *,
    config: BenchmarkConfig | None = None,
    name: str = "HERD candidate",
) -> MatchedCashflowComparison:
    """전략과 B&H에 동일한 외부 현금흐름·비용·기간을 강제한다."""
    cfg = config or BenchmarkConfig()
    strategy = simulate(
        name,
        prices,
        target_weights,
        config=cfg,
        contributions=external_cashflows,
    )
    benchmark = buy_and_hold(
        prices,
        config=cfg,
        contributions=external_cashflows,
    )
    metrics = performance_metrics(strategy, benchmark)
    return MatchedCashflowComparison(
        scenario=scenario,
        strategy=strategy,
        benchmark=benchmark,
        strategy_attribution=attribute_result(strategy),
        benchmark_attribution=attribute_result(benchmark),
        comparison_metrics=metrics,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = validate_contract(load_contract())
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
