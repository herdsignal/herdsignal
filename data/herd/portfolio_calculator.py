"""
herd/portfolio_calculator.py — 포트폴리오 평가금액 계산기

user_portfolio에서 보유 종목과 매수 정보를 조회하고
daily_prices의 최신 종가로 현재 평가금액을 계산한다.
계산 결과는 portfolio_history 테이블에 일별 스냅샷으로 저장된다.

avg_price 또는 quantity가 NULL인 종목 (관심종목 등)은 계산에서 제외.
"""

import logging
import sys
from datetime import date
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from config.database import create_db_engine, get_session_factory  # noqa: E402
from init_db import DailyPrice, PortfolioHistory, UserPortfolio    # noqa: E402

logger = logging.getLogger(__name__)

_SessionFactory = None


def _get_session_factory():
    """실제 포트폴리오 계산 전까지 DB 연결을 만들지 않는다."""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = get_session_factory(create_db_engine())
    return _SessionFactory


def calculate_portfolio_value(user_id: str) -> dict:
    """
    사용자 포트폴리오의 현재 평가금액을 계산하고 portfolio_history에 저장한다.

    Args:
        user_id: 사용자 ID (기본 'local')

    Returns:
        {
            "total_value": float,        # 총 평가금액 (USD)
            "total_cost": float,         # 총 매입금액 (USD)
            "total_return_pct": float,   # 총 수익률 (%)
            "daily_change_pct": float,   # 포트폴리오 일일 등락률 (%)
            "stocks": [
                {
                    "ticker": str,
                    "avg_price": float,       # 평균 매수가
                    "quantity": float,        # 보유 수량
                    "current_price": float,   # 현재가 (최신 종가)
                    "market_value": float,    # 평가금액
                    "return_pct": float,      # 종목 수익률 (%)
                    "daily_change_pct": float # 종목 일일 등락률 (%)
                }
            ]
        }
    """
    today = date.today()

    with _get_session_factory()() as session:
        # avg_price와 quantity 모두 존재하는 보유 종목만 조회
        # (관심종목은 avg_price/quantity가 NULL이므로 자동 제외)
        holdings = (
            session.query(UserPortfolio)
            .filter(
                UserPortfolio.user_id  == user_id,
                UserPortfolio.avg_price.isnot(None),
                UserPortfolio.quantity.isnot(None),
            )
            .order_by(UserPortfolio.ticker)
            .all()
        )

        if not holdings:
            logger.warning(f"[{user_id}] avg_price·quantity가 있는 보유 종목 없음")
            return {
                "total_value":      0.0,
                "total_cost":       0.0,
                "total_return_pct": 0.0,
                "daily_change_pct": 0.0,
                "stocks":           [],
            }

        stocks       = []
        total_value  = 0.0   # 총 평가금액
        total_cost   = 0.0   # 총 매입금액
        prev_total   = 0.0   # 전일 총 평가금액 (일일 등락 계산용)
        curr_for_daily = 0.0  # 전일 데이터 있는 종목만의 현재 총액

        for holding in holdings:
            ticker    = holding.ticker
            avg_price = float(holding.avg_price)
            quantity  = float(holding.quantity)

            # 최신 2일치 종가 조회 (오늘 + 전일 등락 계산용)
            recent = (
                session.query(DailyPrice)
                .filter(DailyPrice.ticker == ticker)
                .order_by(DailyPrice.price_date.desc())
                .limit(2)
                .all()
            )

            if not recent or recent[0].close_price is None:
                logger.warning(f"[{ticker}] daily_prices에 종가 없음 — 계산 제외")
                continue

            current_price = float(recent[0].close_price)
            market_value  = current_price * quantity
            cost          = avg_price * quantity
            return_pct    = (current_price - avg_price) / avg_price * 100

            # 전일 종가로 일일 등락률 계산
            daily_change_pct = 0.0
            if len(recent) >= 2 and recent[1].close_price is not None:
                prev_price = float(recent[1].close_price)
                daily_change_pct = (current_price - prev_price) / prev_price * 100
                # 포트폴리오 일일 등락 집계 (전일 데이터 있는 종목만)
                prev_total     += prev_price * quantity
                curr_for_daily += current_price * quantity

            total_value += market_value
            total_cost  += cost

            stocks.append({
                "ticker":           ticker,
                "avg_price":        avg_price,
                "quantity":         quantity,
                "current_price":    current_price,
                "market_value":     round(market_value,  2),
                "return_pct":       round(return_pct,    4),
                "daily_change_pct": round(daily_change_pct, 4),
            })

        if not stocks:
            logger.warning(f"[{user_id}] 유효한 가격 데이터가 있는 종목 없음")
            return {
                "total_value":      0.0,
                "total_cost":       0.0,
                "total_return_pct": 0.0,
                "daily_change_pct": 0.0,
                "stocks":           [],
            }

        # 전체 합산 지표
        total_return_pct  = (total_value - total_cost) / total_cost * 100
        portfolio_daily   = (
            (curr_for_daily - prev_total) / prev_total * 100
            if prev_total > 0 else 0.0
        )

        # portfolio_history UPSERT (오늘 날짜 기준, 중복 시 업데이트)
        existing = (
            session.query(PortfolioHistory)
            .filter_by(user_id=user_id, snapshot_date=today)
            .first()
        )
        if existing:
            existing.total_value      = round(total_value, 2)
            existing.total_cost       = round(total_cost,  2)
            existing.total_return_pct = round(total_return_pct, 4)
        else:
            session.add(PortfolioHistory(
                user_id          = user_id,
                snapshot_date    = today,
                total_value      = round(total_value, 2),
                total_cost       = round(total_cost,  2),
                total_return_pct = round(total_return_pct, 4),
            ))
        session.commit()

        logger.info(
            f"[{user_id}] 포트폴리오 스냅샷 저장 완료 "
            f"({today}  총 평가 ${total_value:,.2f}  수익률 {total_return_pct:.2f}%)"
        )

    return {
        "total_value":      round(total_value, 2),
        "total_cost":       round(total_cost,  2),
        "total_return_pct": round(total_return_pct, 4),
        "daily_change_pct": round(portfolio_daily,  4),
        "stocks":           stocks,
    }
