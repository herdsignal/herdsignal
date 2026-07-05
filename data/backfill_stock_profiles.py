"""
backfill_stock_profiles.py — stocks 메타데이터 보강 스크립트

기존 stocks 레코드의 name / sector / logo_url이 비어 있을 때
Finnhub company profile2로 회사 프로필을 조회해 채운다.

실행:
    ./scripts/run-data.sh backfill_stock_profiles.py
    ./scripts/run-data.sh backfill_stock_profiles.py --tickers AAPL,NVDA,TSLA
    ./scripts/run-data.sh backfill_stock_profiles.py --all-stocks
"""

import argparse
import logging
from datetime import datetime

from sqlalchemy import select

from collectors.finnhub_collector import get_company_profile
from config.database import create_db_engine, get_session_factory
from init_db import Stock, UserPortfolio, UserWatchlist

logger = logging.getLogger(__name__)


def _normalize_ticker(ticker: str) -> str:
    return (ticker or "").strip().upper()


def _parse_tickers(value: str | None) -> list[str]:
    if not value:
        return []
    tickers = [_normalize_ticker(item) for item in value.split(",")]
    return sorted({ticker for ticker in tickers if ticker})


def _load_default_tickers(session) -> list[str]:
    """
    MVP 화면에서 실제 노출되는 대상만 우선 보강한다.
    S&P 500 전체를 매번 호출하면 Finnhub 무료 플랜 제한에 쉽게 걸릴 수 있다.
    """
    tickers: set[str] = {"SPY"}

    portfolio_rows = session.execute(select(UserPortfolio.ticker)).scalars().all()
    watchlist_rows = session.execute(select(UserWatchlist.ticker)).scalars().all()

    tickers.update(_normalize_ticker(ticker) for ticker in portfolio_rows)
    tickers.update(_normalize_ticker(ticker) for ticker in watchlist_rows)

    return sorted(ticker for ticker in tickers if ticker)


def _load_all_stock_tickers(session) -> list[str]:
    rows = session.execute(
        select(Stock.ticker)
        .where(Stock.is_active.is_(True))
        .order_by(Stock.ticker)
    ).scalars().all()
    return sorted({_normalize_ticker(ticker) for ticker in rows if ticker})


def _ensure_stock(session, ticker: str) -> Stock:
    stock = session.execute(
        select(Stock).where(Stock.ticker == ticker)
    ).scalar_one_or_none()

    if stock is not None:
        return stock

    now = datetime.utcnow()
    stock = Stock(
        ticker=ticker,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(stock)
    session.flush()
    return stock


def backfill_profiles(tickers: list[str]) -> dict:
    engine = create_db_engine()
    SessionFactory = get_session_factory(engine)

    stats = {
        "requested": len(tickers),
        "updated": 0,
        "skipped": 0,
        "missing": 0,
        "failed": 0,
    }

    with SessionFactory() as session:
        for ticker in tickers:
            stock = _ensure_stock(session, ticker)

            if stock.name and stock.sector and stock.logo_url:
                stats["skipped"] += 1
                continue

            try:
                profile = get_company_profile(ticker)
            except Exception as e:
                logger.warning(f"[{ticker}] 회사 프로필 조회 실패: {e}")
                stats["failed"] += 1
                continue

            if not profile:
                logger.info(f"[{ticker}] 회사 프로필 없음")
                stats["missing"] += 1
                continue

            stock.name = stock.name or profile.get("name")
            stock.sector = stock.sector or profile.get("sector")
            stock.logo_url = stock.logo_url or profile.get("logo_url")
            stock.updated_at = datetime.utcnow()
            stats["updated"] += 1
            logger.info(
                f"[{ticker}] 프로필 보강 완료 "
                f"name={bool(stock.name)} sector={bool(stock.sector)} logo={bool(stock.logo_url)}"
            )

        session.commit()

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="stocks 회사명/섹터/로고 URL 백필")
    parser.add_argument("--tickers", help="쉼표로 구분한 티커 목록")
    parser.add_argument("--all-stocks", action="store_true", help="stocks 활성 종목 전체 백필")
    args = parser.parse_args()

    engine = create_db_engine()
    SessionFactory = get_session_factory(engine)

    with SessionFactory() as session:
        if args.tickers:
            tickers = _parse_tickers(args.tickers)
        elif args.all_stocks:
            tickers = _load_all_stock_tickers(session)
        else:
            tickers = _load_default_tickers(session)

    logger.info(f"프로필 백필 대상: {', '.join(tickers) if tickers else '없음'}")
    stats = backfill_profiles(tickers)
    logger.info(f"프로필 백필 결과: {stats}")
    print(stats)


if __name__ == "__main__":
    main()
