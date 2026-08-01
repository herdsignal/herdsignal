"""부분 익절 현금이 재진입까지 이어진 완결 사이클만 평가한다."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import median
from typing import Literal

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


@dataclass(frozen=True)
class ExplicitCycleEvent:
    """실제·shadow 사이클에서 다른 현금과 섞일 수 없는 명시적 사건."""

    event_id: str
    cycle_id: str
    ticker: str
    session_index: int
    occurred_on: date
    event_type: Literal["TRIM", "REENTRY"]
    shares: float
    notional: float
    fee: float = 0.0


@dataclass(frozen=True)
class MatchedCashCycle:
    cycle_id: str
    ticker: str
    status: Literal["CASH_RESERVED", "PARTIAL_REENTRY", "COMPLETED", "EXPIRED"]
    trim_session_index: int
    trim_date: date
    expiry_session_index: int
    sold_shares: float
    net_sale_cash: float
    reentry_cost: float
    remaining_cash: float
    reentered_shares: float
    completion_date: date | None
    share_delta: float | None


@dataclass(frozen=True)
class MatchedCashLedgerAudit:
    cycles: tuple[MatchedCashCycle, ...]
    reserved_cash: float
    expired_cash: float
    completed_cycle_count: int
    expired_cycle_count: int


@dataclass
class _MutableExplicitCycle:
    cycle_id: str
    ticker: str
    trim_session_index: int
    trim_date: date
    expiry_session_index: int
    sold_shares: float
    net_sale_cash: float
    reentry_cost: float = 0.0
    reentered_shares: float = 0.0
    completion_date: date | None = None


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


def replay_matched_cash_cycles(
    events: list[ExplicitCycleEvent],
    *,
    as_of_session_index: int,
    maximum_reentry_wait_sessions: int = 126,
    cash_tolerance: float = 1e-6,
) -> MatchedCashLedgerAudit:
    """익절 현금과 재진입을 명시적 cycle ID로만 연결한다.

    FIFO 추정은 연구 백테스트 호환 함수에만 남긴다. 실제·shadow 원장은
    다른 종목, 외부 입금 또는 다른 익절의 현금이 섞이면 즉시 실패한다.
    """
    if maximum_reentry_wait_sessions <= 0:
        raise ValueError("maximum_reentry_wait_sessions must be positive")
    if cash_tolerance <= 0:
        raise ValueError("cash_tolerance must be positive")
    if as_of_session_index < 0:
        raise ValueError("as_of_session_index must be non-negative")
    if len({event.event_id for event in events}) != len(events):
        raise ValueError("event_id must be unique")

    ordered = sorted(
        enumerate(events),
        key=lambda item: (
            item[1].session_index,
            item[1].occurred_on,
            item[0],
        ),
    )
    cycles: dict[str, _MutableExplicitCycle] = {}
    for _, event in ordered:
        _validate_explicit_event(event, as_of_session_index)
        if event.event_type == "TRIM":
            if event.cycle_id in cycles:
                raise ValueError(f"duplicate cycle_id: {event.cycle_id}")
            net_cash = event.notional - event.fee
            if net_cash <= cash_tolerance:
                raise ValueError("trim must create positive net cash")
            cycles[event.cycle_id] = _MutableExplicitCycle(
                cycle_id=event.cycle_id,
                ticker=event.ticker.upper(),
                trim_session_index=event.session_index,
                trim_date=event.occurred_on,
                expiry_session_index=(
                    event.session_index + maximum_reentry_wait_sessions
                ),
                sold_shares=event.shares,
                net_sale_cash=net_cash,
            )
            continue

        cycle = cycles.get(event.cycle_id)
        if cycle is None:
            raise ValueError(f"reentry has no matched trim: {event.cycle_id}")
        if event.ticker.upper() != cycle.ticker:
            raise ValueError("reentry ticker must match trim ticker")
        if event.session_index <= cycle.trim_session_index:
            raise ValueError("reentry must occur after trim")
        if event.session_index > cycle.expiry_session_index:
            raise ValueError("reentry occurred after cycle expiry")
        if cycle.completion_date is not None:
            raise ValueError("completed cycle cannot accept another reentry")

        cost = event.notional + event.fee
        remaining = cycle.net_sale_cash - cycle.reentry_cost
        if cost > remaining + cash_tolerance:
            raise ValueError("reentry cannot use external or unmatched cash")
        cycle.reentry_cost += min(cost, remaining)
        cycle.reentered_shares += event.shares
        if cycle.net_sale_cash - cycle.reentry_cost <= cash_tolerance:
            cycle.reentry_cost = cycle.net_sale_cash
            cycle.completion_date = event.occurred_on

    frozen = tuple(
        _freeze_explicit_cycle(cycle, as_of_session_index, cash_tolerance)
        for cycle in sorted(
            cycles.values(),
            key=lambda item: (item.trim_session_index, item.cycle_id),
        )
    )
    return MatchedCashLedgerAudit(
        cycles=frozen,
        reserved_cash=sum(
            cycle.remaining_cash
            for cycle in frozen
            if cycle.status in {"CASH_RESERVED", "PARTIAL_REENTRY"}
        ),
        expired_cash=sum(
            cycle.remaining_cash for cycle in frozen if cycle.status == "EXPIRED"
        ),
        completed_cycle_count=sum(cycle.status == "COMPLETED" for cycle in frozen),
        expired_cycle_count=sum(cycle.status == "EXPIRED" for cycle in frozen),
    )


def _validate_explicit_event(
    event: ExplicitCycleEvent, as_of_session_index: int
) -> None:
    if not event.event_id.strip() or not event.cycle_id.strip():
        raise ValueError("event_id and cycle_id are required")
    if not event.ticker.strip():
        raise ValueError("ticker is required")
    if event.event_type not in {"TRIM", "REENTRY"}:
        raise ValueError(f"unsupported cycle event: {event.event_type}")
    if event.session_index < 0 or event.session_index > as_of_session_index:
        raise ValueError("event session must be inside the observed ledger")
    if event.shares <= 0 or event.notional <= 0 or event.fee < 0:
        raise ValueError("shares and notional must be positive and fee non-negative")


def _freeze_explicit_cycle(
    cycle: _MutableExplicitCycle,
    as_of_session_index: int,
    cash_tolerance: float,
) -> MatchedCashCycle:
    remaining = max(0.0, cycle.net_sale_cash - cycle.reentry_cost)
    if cycle.completion_date is not None:
        status = "COMPLETED"
        share_delta = cycle.reentered_shares - cycle.sold_shares
    elif as_of_session_index > cycle.expiry_session_index:
        status = "EXPIRED"
        share_delta = None
    elif cycle.reentry_cost > cash_tolerance:
        status = "PARTIAL_REENTRY"
        share_delta = None
    else:
        status = "CASH_RESERVED"
        share_delta = None
    return MatchedCashCycle(
        cycle_id=cycle.cycle_id,
        ticker=cycle.ticker,
        status=status,
        trim_session_index=cycle.trim_session_index,
        trim_date=cycle.trim_date,
        expiry_session_index=cycle.expiry_session_index,
        sold_shares=cycle.sold_shares,
        net_sale_cash=cycle.net_sale_cash,
        reentry_cost=cycle.reentry_cost,
        remaining_cash=remaining,
        reentered_shares=cycle.reentered_shares,
        completion_date=cycle.completion_date,
        share_delta=share_delta,
    )
