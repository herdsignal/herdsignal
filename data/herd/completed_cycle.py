"""부분 익절 현금이 재진입까지 이어진 완결 사이클만 평가한다."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import median

from herd.benchmark_engine import Trade


@dataclass
class _OpenSale:
    sale_date: date
    sold_shares: float
    net_proceeds: float
    remaining_cash: float
    bought_shares: float = 0.0
    reentry_cost: float = 0.0
    completion_date: date | None = None


@dataclass(frozen=True)
class CompletedCycle:
    sale_date: date
    completion_date: date
    days_out: int
    sold_shares: float
    reentered_shares: float
    share_delta: float
    net_sale_proceeds: float
    reentry_cost: float


@dataclass(frozen=True)
class CycleAudit:
    completed_cycles: tuple[CompletedCycle, ...]
    open_sale_count: int
    open_sale_cash: float
    unmatched_buy_cost: float


def match_completed_cycles(
    trades: list[Trade],
    *,
    cash_tolerance: float = 1e-6,
) -> CycleAudit:
    """매도 순현금을 이후 매수 총비용에 FIFO로 연결한다."""
    if cash_tolerance <= 0:
        raise ValueError("cash_tolerance must be positive")

    ordered = sorted(
        enumerate(trades),
        key=lambda item: (item[1].execution_date, item[0]),
    )
    open_sales: list[_OpenSale] = []
    completed: list[CompletedCycle] = []
    unmatched_buy_cost = 0.0

    for _, trade in ordered:
        side = trade.side.upper()
        execution_date = trade.execution_date.date()
        if side == "SELL":
            proceeds = trade.notional - trade.fee
            if proceeds > cash_tolerance and trade.shares > 0:
                open_sales.append(_OpenSale(
                    sale_date=execution_date,
                    sold_shares=trade.shares,
                    net_proceeds=proceeds,
                    remaining_cash=proceeds,
                ))
            continue
        if side != "BUY":
            continue
        if trade.signal_date is None:
            # 공통 초기 보유 구축은 재진입이 아니다.
            continue

        buy_cost = trade.notional + trade.fee
        remaining_buy_cost = buy_cost
        for sale in open_sales:
            if sale.remaining_cash <= cash_tolerance or remaining_buy_cost <= cash_tolerance:
                continue
            allocation = min(sale.remaining_cash, remaining_buy_cost)
            allocated_shares = trade.shares * allocation / buy_cost
            sale.remaining_cash -= allocation
            sale.reentry_cost += allocation
            sale.bought_shares += allocated_shares
            remaining_buy_cost -= allocation
            if sale.remaining_cash <= cash_tolerance:
                sale.remaining_cash = 0.0
                sale.completion_date = execution_date
                completed.append(CompletedCycle(
                    sale_date=sale.sale_date,
                    completion_date=execution_date,
                    days_out=(execution_date - sale.sale_date).days,
                    sold_shares=sale.sold_shares,
                    reentered_shares=sale.bought_shares,
                    share_delta=sale.bought_shares - sale.sold_shares,
                    net_sale_proceeds=sale.net_proceeds,
                    reentry_cost=sale.reentry_cost,
                ))
        unmatched_buy_cost += max(0.0, remaining_buy_cost)
        open_sales = [sale for sale in open_sales if sale.remaining_cash > cash_tolerance]

    return CycleAudit(
        completed_cycles=tuple(completed),
        open_sale_count=len(open_sales),
        open_sale_cash=sum(sale.remaining_cash for sale in open_sales),
        unmatched_buy_cost=unmatched_buy_cost,
    )


def cycle_metrics(audit: CycleAudit) -> dict[str, float | int | None]:
    cycles = audit.completed_cycles
    return {
        "completed_cycle_count": len(cycles),
        "positive_share_cycle_count": sum(cycle.share_delta > 0 for cycle in cycles),
        "completed_cycle_share_delta": sum(cycle.share_delta for cycle in cycles),
        "median_days_out": (
            float(median(cycle.days_out for cycle in cycles))
            if cycles else None
        ),
        "open_sale_count": audit.open_sale_count,
        "open_sale_cash": audit.open_sale_cash,
        "unmatched_buy_cost": audit.unmatched_buy_cost,
    }
