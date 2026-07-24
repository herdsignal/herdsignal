"""실시간 포트폴리오 평가의 조회·계산·저장 경계."""

from __future__ import annotations

import logging
from datetime import date

from init_db import PortfolioHistory, UserPortfolio

logger = logging.getLogger(__name__)


def load_holdings(user_id: str, session_factory) -> list[dict]:
    """세션이 닫힌 뒤에도 사용할 수 있는 보유 종목 값 객체를 반환한다."""
    with session_factory() as session:
        rows = (
            session.query(UserPortfolio)
            .filter(
                UserPortfolio.user_id == user_id,
                UserPortfolio.avg_price.isnot(None),
                UserPortfolio.quantity.isnot(None),
            )
            .order_by(UserPortfolio.ticker)
            .all()
        )
        return [
            {
                "ticker": row.ticker,
                "avg_price": float(row.avg_price),
                "quantity": float(row.quantity),
            }
            for row in rows
        ]


def value_holdings(holdings: list[dict], prices: dict) -> tuple[list[dict], dict]:
    """시세가 존재하는 보유 종목을 평가하고 포트폴리오 합계를 계산한다."""
    stocks: list[dict] = []
    totals = {
        "total_value": 0.0,
        "total_cost": 0.0,
        "previous_value": 0.0,
        "daily_current_value": 0.0,
    }
    for holding in holdings:
        ticker = holding["ticker"]
        price = prices.get(ticker)
        if price is None:
            logger.warning("[RealtimePortfolio][%s] 현재가 조회 실패 — 계산 제외", ticker)
            continue

        avg_price = holding["avg_price"]
        quantity = holding["quantity"]
        current_price = price["price"]
        market_value = current_price * quantity
        cost = avg_price * quantity
        return_pct = (current_price - avg_price) / avg_price * 100

        totals["total_value"] += market_value
        totals["total_cost"] += cost
        totals["previous_value"] += price["prev_close"] * quantity
        totals["daily_current_value"] += current_price * quantity
        stocks.append({
            "ticker": ticker,
            "avg_price": avg_price,
            "quantity": quantity,
            "current_price": round(current_price, 4),
            "price_date": price["price_date"],
            "market_value": round(market_value, 2),
            "return_pct": round(return_pct, 4),
            "daily_change_pct": round(price["change_pct"], 4),
        })
    return stocks, totals


def upsert_snapshot(
    user_id: str,
    snapshot_date: date,
    total_value: float,
    total_cost: float,
    total_return_pct: float,
    session_factory,
) -> None:
    """동일 사용자·날짜의 스냅샷을 원자적으로 갱신한다."""
    with session_factory() as session:
        existing = (
            session.query(PortfolioHistory)
            .filter_by(user_id=user_id, snapshot_date=snapshot_date)
            .first()
        )
        if existing:
            existing.total_value = round(total_value, 2)
            existing.total_cost = round(total_cost, 2)
            existing.total_return_pct = round(total_return_pct, 4)
        else:
            session.add(PortfolioHistory(
                user_id=user_id,
                snapshot_date=snapshot_date,
                total_value=round(total_value, 2),
                total_cost=round(total_cost, 2),
                total_return_pct=round(total_return_pct, 4),
            ))
        session.commit()


def empty_portfolio() -> dict:
    return {
        "total_value": 0.0,
        "total_cost": 0.0,
        "total_return_pct": 0.0,
        "daily_change_pct": 0.0,
        "stocks": [],
    }
