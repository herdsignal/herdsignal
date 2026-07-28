"""실시간 포트폴리오 평가의 조회·계산·저장 경계."""

from __future__ import annotations

import logging
from datetime import date
from typing import Callable

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
        "market_data_date": None,
        "expected_stock_count": 0,
        "priced_stock_count": 0,
        "missing_price_tickers": [],
        "valuation_status": "EMPTY",
        "stocks": [],
    }


def calculate_current_portfolio(
    user_id: str,
    *,
    session_factory,
    price_loader: Callable[[list[str]], dict],
    snapshot_date: date | None = None,
) -> dict:
    """현재가로 포트폴리오를 평가하고 같은 날짜의 스냅샷을 갱신한다."""
    effective_date = snapshot_date or date.today()
    holdings = load_holdings(user_id, session_factory)
    if not holdings:
        logger.warning("[Tier3][%s] 평가 가능한 보유 종목 없음", user_id)
        return empty_portfolio()

    expected_tickers = [holding["ticker"] for holding in holdings]
    prices = price_loader(expected_tickers)
    stocks, totals = value_holdings(holdings, prices)
    if not stocks:
        logger.warning("[Tier3][%s] 유효한 현재가가 있는 종목 없음", user_id)
        return {
            **empty_portfolio(),
            "expected_stock_count": len(expected_tickers),
            "missing_price_tickers": expected_tickers,
            "valuation_status": "UNAVAILABLE",
        }

    total_value = totals["total_value"]
    total_cost = totals["total_cost"]
    priced_tickers = {stock["ticker"] for stock in stocks}
    missing_price_tickers = [
        ticker for ticker in expected_tickers if ticker not in priced_tickers
    ]
    valuation_status = "PARTIAL" if missing_price_tickers else "COMPLETE"
    total_return_pct = (
        (total_value - total_cost) / total_cost * 100
        if total_cost > 0
        else 0.0
    )
    daily_change_pct = (
        (totals["daily_current_value"] - totals["previous_value"])
        / totals["previous_value"]
        * 100
        if totals["previous_value"] > 0
        else 0.0
    )
    if valuation_status == "COMPLETE":
        upsert_snapshot(
            user_id,
            effective_date,
            total_value,
            total_cost,
            total_return_pct,
            session_factory,
        )
    else:
        logger.warning(
            "[Tier3][%s] 일부 시세 누락으로 자산 스냅샷 저장 생략: %s",
            user_id,
            ", ".join(missing_price_tickers),
        )
    logger.info(
        "[Tier3][%s] 보유 %s종목 총 평가 $%s 수익률 %.2f%%",
        user_id,
        len(stocks),
        f"{total_value:,.2f}",
        total_return_pct,
    )
    return {
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "total_return_pct": round(total_return_pct, 4),
        "daily_change_pct": round(daily_change_pct, 4),
        "market_data_date": min(stock["price_date"] for stock in stocks),
        "expected_stock_count": len(expected_tickers),
        "priced_stock_count": len(stocks),
        "missing_price_tickers": missing_price_tickers,
        "valuation_status": valuation_status,
        "stocks": stocks,
    }
