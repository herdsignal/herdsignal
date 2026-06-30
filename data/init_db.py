"""
init_db.py — 테이블 초기화 스크립트
HerdSignal 서비스에 필요한 7개 테이블을 생성한다.
이미 존재하는 테이블은 건드리지 않는다 (CREATE TABLE IF NOT EXISTS).

실행:
    cd data/
    python init_db.py              # settings.py의 DATABASE_URL 사용 (MariaDB)
    python init_db.py --sqlite     # SQLite 로컬 테스트용
"""

import argparse
import logging
import sys
from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Date,
    Index, String, UniqueConstraint,
)
from sqlalchemy import Numeric as Decimal

from config.database import Base, create_db_engine

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 1. 종목 마스터 (stocks)
# ──────────────────────────────────────────────
class Stock(Base):
    """미국주식 종목 마스터. 서비스에서 추적하는 모든 종목을 등록."""
    __tablename__ = "stocks"

    id                  = Column(BigInteger, primary_key=True, autoincrement=True, comment="PK")
    ticker              = Column(String(10),  nullable=False, unique=True,          comment="티커 심볼 (AAPL, NVDA 등)")
    name                = Column(String(100), nullable=True,                         comment="종목 정식 명칭")
    sector              = Column(String(50),  nullable=True,                         comment="섹터 (Technology, Healthcare 등)")
    market_cap_category = Column(String(20),  nullable=True,                         comment="대형주 / 중형주 / 소형주")
    is_active           = Column(Boolean,     nullable=False, default=True,          comment="추적 활성 여부 (비활성화 시 False)")
    created_at          = Column(DateTime,    nullable=False, default=datetime.utcnow, comment="레코드 생성 시각 (UTC)")
    updated_at          = Column(DateTime,    nullable=False, default=datetime.utcnow,
                                 onupdate=datetime.utcnow,                           comment="마지막 수정 시각 (UTC)")


# ──────────────────────────────────────────────
# 2. HERD 점수 히스토리 (herd_scores)
# ──────────────────────────────────────────────
class HerdScore(Base):
    """날짜별 HERD Index 점수 및 단계 판정 결과."""
    __tablename__ = "herd_scores"
    __table_args__ = (
        UniqueConstraint("ticker", "score_date", name="uq_herd_scores_ticker_date"),
        Index("ix_herd_scores_ticker_date_desc", "ticker", "score_date"),
        {"comment": "날짜별 HERD Index 점수 히스토리"},
    )

    id          = Column(BigInteger,    primary_key=True, autoincrement=True, comment="PK")
    ticker      = Column(String(10),    nullable=False,                        comment="티커 심볼")
    score_date  = Column(Date,          nullable=False,                        comment="점수 산출 기준 날짜")
    herd_score  = Column(Decimal(5, 2), nullable=False,                        comment="HERD 점수 (0.00 ~ 100.00)")
    herd_stage  = Column(String(20),    nullable=False,                        comment="단계 (Flee/Scatter/Calm/Drift/Rush)")
    signal      = Column(String(20),    nullable=True,                         comment="매매 신호 (BUY/SELL/HOLD/NULL)")
    created_at  = Column(DateTime,      nullable=False, default=datetime.utcnow, comment="레코드 생성 시각 (UTC)")


# ──────────────────────────────────────────────
# 3. 지표 분해값 (herd_indicators)
# ──────────────────────────────────────────────
class HerdIndicator(Base):
    """HERD 점수를 구성하는 5개 지표의 날짜별 개별 값."""
    __tablename__ = "herd_indicators"
    __table_args__ = (
        UniqueConstraint("ticker", "score_date", name="uq_herd_indicators_ticker_date"),
        {"comment": "HERD 점수 구성 지표 분해값 (디버깅·분석용)"},
    )

    id               = Column(BigInteger,    primary_key=True, autoincrement=True, comment="PK")
    ticker           = Column(String(10),    nullable=False,                        comment="티커 심볼")
    score_date       = Column(Date,          nullable=False,                        comment="지표 산출 기준 날짜")
    weekly_rsi       = Column(Decimal(5, 2), nullable=True,                         comment="주봉 RSI 정규화값 (0~100)")
    monthly_rsi      = Column(Decimal(5, 2), nullable=True,                         comment="월봉 RSI 정규화값 (0~100)")
    position_52w     = Column(Decimal(5, 2), nullable=True,                         comment="52주 고저 위치 정규화값 (0~100)")
    ma200_deviation  = Column(Decimal(5, 2), nullable=True,                         comment="MA200 이격도 정규화값 (0~100)")
    volume_strength  = Column(Decimal(5, 2), nullable=True,                         comment="거래량 강도 정규화값 (0~100)")
    created_at       = Column(DateTime,      nullable=False, default=datetime.utcnow, comment="레코드 생성 시각 (UTC)")


# ──────────────────────────────────────────────
# 4. 일봉 가격 데이터 (daily_prices)
# ──────────────────────────────────────────────
class DailyPrice(Base):
    """yfinance에서 수집한 일봉 OHLCV 데이터."""
    __tablename__ = "daily_prices"
    __table_args__ = (
        UniqueConstraint("ticker", "price_date", name="uq_daily_prices_ticker_date"),
        Index("ix_daily_prices_ticker_date_desc", "ticker", "price_date"),
        {"comment": "일봉 OHLCV 가격 데이터 (yfinance 수집)"},
    )

    id          = Column(BigInteger,     primary_key=True, autoincrement=True, comment="PK")
    ticker      = Column(String(10),     nullable=False,                        comment="티커 심볼")
    price_date  = Column(Date,           nullable=False,                        comment="거래일 날짜")
    open_price  = Column(Decimal(12, 4), nullable=True,                         comment="시가")
    high_price  = Column(Decimal(12, 4), nullable=True,                         comment="고가")
    low_price   = Column(Decimal(12, 4), nullable=True,                         comment="저가")
    close_price = Column(Decimal(12, 4), nullable=True,                         comment="종가 (수정 종가)")
    volume      = Column(BigInteger,     nullable=True,                         comment="거래량")
    created_at  = Column(DateTime,       nullable=False, default=datetime.utcnow, comment="레코드 생성 시각 (UTC)")


# ──────────────────────────────────────────────
# 5. 보유 종목 (user_portfolio)
# ──────────────────────────────────────────────
class UserPortfolio(Base):
    """사용자 보유 종목. 멀티유저 대비 user_id 컬럼 포함."""
    __tablename__ = "user_portfolio"
    __table_args__ = (
        UniqueConstraint("user_id", "ticker", name="uq_portfolio_user_ticker"),
        {"comment": "사용자 보유 종목 및 매수 정보"},
    )

    id          = Column(BigInteger,     primary_key=True, autoincrement=True, comment="PK")
    user_id     = Column(String(50),     nullable=False, default="local",       comment="사용자 ID (기본값: local)")
    ticker      = Column(String(10),     nullable=False,                        comment="티커 심볼")
    avg_price   = Column(Decimal(12, 4), nullable=True,                         comment="평균 매수가 (USD)")
    quantity    = Column(Decimal(12, 4), nullable=True,                         comment="보유 수량 (소수점 지원)")
    memo        = Column(String(200),    nullable=True,                         comment="메모")
    created_at  = Column(DateTime,       nullable=False, default=datetime.utcnow, comment="레코드 생성 시각 (UTC)")
    updated_at  = Column(DateTime,       nullable=False, default=datetime.utcnow,
                         onupdate=datetime.utcnow,                              comment="마지막 수정 시각 (UTC)")


# ──────────────────────────────────────────────
# 6. 관심 종목 (user_watchlist)
# ──────────────────────────────────────────────
class UserWatchlist(Base):
    """사용자 관심 종목 목록."""
    __tablename__ = "user_watchlist"
    __table_args__ = (
        UniqueConstraint("user_id", "ticker", name="uq_watchlist_user_ticker"),
        {"comment": "사용자 관심 종목 목록"},
    )

    id          = Column(BigInteger,  primary_key=True, autoincrement=True, comment="PK")
    user_id     = Column(String(50),  nullable=False, default="local",       comment="사용자 ID (기본값: local)")
    ticker      = Column(String(10),  nullable=False,                        comment="티커 심볼")
    memo        = Column(String(200), nullable=True,                         comment="메모")
    created_at  = Column(DateTime,    nullable=False, default=datetime.utcnow, comment="레코드 생성 시각 (UTC)")


# ──────────────────────────────────────────────
# 7. 포트폴리오 일별 스냅샷 (portfolio_history)
# ──────────────────────────────────────────────
class PortfolioHistory(Base):
    """
    사용자 포트폴리오 일별 평가금액 스냅샷.
    매일 스케줄러 실행 후 자동 저장. 수익률 추이 시각화에 사용.
    (user_id, snapshot_date) 복합 UNIQUE → 날짜당 1개 레코드 보장.
    """
    __tablename__ = "portfolio_history"
    __table_args__ = (
        UniqueConstraint("user_id", "snapshot_date", name="uq_portfolio_history_user_date"),
        {"comment": "포트폴리오 일별 평가금액 히스토리 (daily 스냅샷)"},
    )

    id               = Column(BigInteger,     primary_key=True, autoincrement=True, comment="PK")
    user_id          = Column(String(50),     nullable=False,                        comment="사용자 ID")
    snapshot_date    = Column(Date,           nullable=False,                        comment="스냅샷 기준일")
    total_value      = Column(Decimal(15, 2), nullable=False,                        comment="총 평가금액 (USD)")
    total_cost       = Column(Decimal(15, 2), nullable=False,                        comment="총 매입금액 (USD)")
    total_return_pct = Column(Decimal(8, 4),  nullable=False,                        comment="총 수익률 (%)")
    created_at       = Column(DateTime,       nullable=False, default=datetime.utcnow, comment="레코드 생성 시각 (UTC)")


# ──────────────────────────────────────────────
# 테이블 생성 실행
# ──────────────────────────────────────────────
SQLITE_PATH = "herdsignal_test.db"

MODELS = [
    Stock, HerdScore, HerdIndicator, DailyPrice,
    UserPortfolio, UserWatchlist, PortfolioHistory,
]


def init_tables(engine) -> None:
    """Base.metadata.create_all로 모든 테이블을 생성한다."""
    logger.info("테이블 생성 시작...")
    Base.metadata.create_all(bind=engine)
    logger.info("테이블 생성 완료")


def verify_tables(engine) -> None:
    """생성된 테이블 목록을 로그로 확인한다."""
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    logger.info(f"생성된 테이블 {len(tables)}개: {tables}")
    for table in tables:
        cols = inspector.get_columns(table)
        logger.info(f"  {table}: {[c['name'] for c in cols]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HerdSignal DB 테이블 초기화")
    parser.add_argument(
        "--sqlite",
        action="store_true",
        help=f"SQLite 로컬 테스트 모드 (파일: {SQLITE_PATH})",
    )
    args = parser.parse_args()

    if args.sqlite:
        url = f"sqlite:///{SQLITE_PATH}"
        logger.info(f"[SQLite 모드] {url}")
    else:
        from config.settings import DATABASE_URL
        url = DATABASE_URL
        logger.info("[MariaDB 모드]")

    try:
        engine = create_db_engine(url)
        init_tables(engine)
        verify_tables(engine)
        print("\n테이블 초기화 완료")
    except Exception as e:
        print(f"\n실패: {e}", file=sys.stderr)
        sys.exit(1)
