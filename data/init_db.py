"""
init_db.py — 테이블 초기화 스크립트
HerdSignal 서비스에 필요한 테이블을 생성한다.
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
    BigInteger, Boolean, Column, DateTime, Date, Integer,
    Index, String, Text, UniqueConstraint, text,
)
from sqlalchemy import Numeric as Decimal

from config.database import Base, create_db_engine

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 1. 로그인 사용자 (app_users)
# ──────────────────────────────────────────────
class AppUser(Base):
    """Google 로그인으로 생성되는 서비스 사용자."""
    __tablename__ = "app_users"
    __table_args__ = (
        UniqueConstraint("provider", "provider_subject", name="uk_app_users_provider_subject"),
        Index("ix_app_users_email", "email"),
    )

    id                = Column(String(36),   primary_key=True)
    provider          = Column(String(20),   nullable=False)
    provider_subject  = Column(String(100),  nullable=False)
    email             = Column(String(255),  nullable=False)
    display_name      = Column(String(100),  nullable=False)
    profile_image_url = Column(String(1000), nullable=True)
    role              = Column(String(20),   nullable=False, default="USER")
    created_at        = Column(DateTime,     nullable=False, default=datetime.utcnow)
    last_login_at     = Column(DateTime,     nullable=False, default=datetime.utcnow)


# ──────────────────────────────────────────────
# 2. 종목 마스터 (stocks)
# ──────────────────────────────────────────────
class Stock(Base):
    """미국주식 종목 마스터. 서비스에서 추적하는 모든 종목을 등록."""
    __tablename__ = "stocks"

    id                  = Column(BigInteger, primary_key=True, autoincrement=True, comment="PK")
    ticker              = Column(String(10),  nullable=False, unique=True,          comment="티커 심볼 (AAPL, NVDA 등)")
    name                = Column(String(100), nullable=True,                         comment="종목 정식 명칭")
    sector              = Column(String(50),  nullable=True,                         comment="섹터 (Technology, Healthcare 등)")
    logo_url            = Column(String(300), nullable=True,                         comment="회사 로고 URL")
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
    """HERD 점수를 구성하는 지표의 날짜별 개별 값."""
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
    ma200_weekly     = Column(Decimal(5, 2), nullable=True,                         comment="200주 MA 위치 정규화값 (0~100)")
    herd_base         = Column(Decimal(5, 2), nullable=True,                         comment="HERD v3 기본 점수")
    eps_multiplier    = Column(Decimal(5, 2), nullable=True,                         comment="EPS 서프라이즈 보정 승수")
    sector_multiplier = Column(Decimal(5, 2), nullable=True,                         comment="섹터 상대 강도 보정 승수")
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


class SchedulerRun(Base):
    """Tier1 스케줄러 실행 단위별 상태와 처리 결과."""
    __tablename__ = "scheduler_runs"
    __table_args__ = (
        Index("ix_scheduler_runs_job_started", "job_name", "started_at"),
        {"comment": "스케줄러 실행 이력"},
    )

    id             = Column(BigInteger, primary_key=True, autoincrement=True)
    job_name       = Column(String(50), nullable=False)
    trigger_type   = Column(String(20), nullable=False)
    status         = Column(String(30), nullable=False)
    started_at     = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at    = Column(DateTime, nullable=True)
    total_count    = Column(Integer, nullable=False, default=0)
    success_count  = Column(Integer, nullable=False, default=0)
    failed_count   = Column(Integer, nullable=False, default=0)
    failed_tickers = Column(Text, nullable=True)
    error_message  = Column(Text, nullable=True)


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


class InvestorProfile(Base):
    """로그인 도입 전 local 사용자에게 적용할 행동 보조 설정."""
    __tablename__ = "investor_profiles"

    user_id = Column(String(50), primary_key=True, comment="사용자 ID")
    strategy = Column(String(30), nullable=False, default="EXISTING_HOLDER")
    risk_tolerance = Column(String(20), nullable=False, default="BALANCED")
    time_horizon_years = Column(Integer, nullable=False, default=10)
    liquidity_buffer_months = Column(Integer, nullable=False, default=6)
    max_action_ratio = Column(Decimal(5, 4), nullable=False, default=0.15)
    target_equity_ratio = Column(Decimal(5, 4), nullable=False, default=0.70)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


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
# 7. 현금 보유액 현재값 (user_cash_balance)
# ──────────────────────────────────────────────
class UserCashBalance(Base):
    """사용자 현금 보유액 현재값."""
    __tablename__ = "user_cash_balance"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_cash_balance_user"),
        {"comment": "사용자 현금 보유액 현재값"},
    )

    id          = Column(BigInteger,     primary_key=True, autoincrement=True, comment="PK")
    user_id     = Column(String(50),     nullable=False,                        comment="사용자 ID")
    cash_amount = Column(Decimal(15, 2), nullable=False, default=0,              comment="현금 보유액 (USD)")
    created_at  = Column(DateTime,       nullable=False, default=datetime.utcnow, comment="레코드 생성 시각 (UTC)")
    updated_at  = Column(DateTime,       nullable=False, default=datetime.utcnow,
                         onupdate=datetime.utcnow,                              comment="마지막 수정 시각 (UTC)")


# ──────────────────────────────────────────────
# 8. 현금 보유액 일별 스냅샷 (user_cash_history)
# ──────────────────────────────────────────────
class UserCashHistory(Base):
    """사용자 현금 보유액 일별 스냅샷."""
    __tablename__ = "user_cash_history"
    __table_args__ = (
        UniqueConstraint("user_id", "snapshot_date", name="uq_user_cash_history_user_date"),
        {"comment": "사용자 현금 보유액 일별 스냅샷"},
    )

    id            = Column(BigInteger,     primary_key=True, autoincrement=True, comment="PK")
    user_id       = Column(String(50),     nullable=False,                        comment="사용자 ID")
    snapshot_date = Column(Date,           nullable=False,                        comment="스냅샷 기준일")
    cash_amount   = Column(Decimal(15, 2), nullable=False, default=0,              comment="현금 보유액 (USD)")
    created_at    = Column(DateTime,       nullable=False, default=datetime.utcnow, comment="레코드 생성 시각 (UTC)")
    updated_at    = Column(DateTime,       nullable=False, default=datetime.utcnow,
                           onupdate=datetime.utcnow,                              comment="마지막 수정 시각 (UTC)")


# ──────────────────────────────────────────────
# 9. 포트폴리오 일별 스냅샷 (portfolio_history)
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
# 10. HERD 판단 기록 (signal_journal)
# ──────────────────────────────────────────────
class SignalJournal(Base):
    """사용자가 HERD 신호를 보고 남긴 매수/보류/익절 판단 기록."""
    __tablename__ = "signal_journal"
    __table_args__ = (
        Index("ix_signal_journal_user_recorded", "user_id", "recorded_at"),
        Index("ix_signal_journal_user_ticker_recorded", "user_id", "ticker", "recorded_at"),
        {"comment": "사용자 HERD 판단 기록"},
    )

    id                   = Column(BigInteger,      primary_key=True, autoincrement=True, comment="PK")
    user_id              = Column(String(50),      nullable=False, default="local",       comment="사용자 ID")
    ticker               = Column(String(10),      nullable=False,                        comment="티커 심볼")
    action_type          = Column(String(20),      nullable=False,                        comment="판단 유형 (BUY/HOLD/SELL)")
    action_label         = Column(String(50),      nullable=True,                         comment="화면 표시용 행동 문구")
    score_date           = Column(Date,            nullable=True,                         comment="HERD 점수 기준일")
    herd_score           = Column(Decimal(5, 2),   nullable=True,                         comment="기록 당시 HERD 점수")
    herd_stage           = Column(String(20),      nullable=True,                         comment="기록 당시 HERD 단계")
    signal               = Column(String(20),      nullable=True,                         comment="기록 당시 HERD 신호")
    signal_label         = Column(String(100),     nullable=True,                         comment="기록 당시 신호 문구")
    action_ratio         = Column(Decimal(6, 4),   nullable=True,                         comment="기록 당시 권장 행동 비율")
    signal_duration_days = Column(BigInteger,      nullable=True,                         comment="기록 당시 신호 지속일")
    stage_duration_days  = Column(BigInteger,      nullable=True,                         comment="기록 당시 단계 지속일")
    price                = Column(Decimal(12, 4),  nullable=True,                         comment="기록 가격 (USD)")
    quantity             = Column(Decimal(12, 4),  nullable=True,                         comment="기록 수량")
    amount               = Column(Decimal(15, 2),  nullable=True,                         comment="기록 총액 (USD)")
    profit_pct           = Column(Decimal(8, 4),   nullable=True,                         comment="익절/매매 수익률 (%)")
    memo                 = Column(String(1000),    nullable=True,                         comment="사용자 메모")
    recorded_at          = Column(DateTime,        nullable=False, default=datetime.utcnow, comment="판단 기록 시각 (UTC)")
    created_at           = Column(DateTime,        nullable=False, default=datetime.utcnow, comment="레코드 생성 시각 (UTC)")
    updated_at           = Column(DateTime,        nullable=False, default=datetime.utcnow,
                                  onupdate=datetime.utcnow,                               comment="마지막 수정 시각 (UTC)")


# ──────────────────────────────────────────────
# 테이블 생성 실행
# ──────────────────────────────────────────────
SQLITE_PATH = "herdsignal_test.db"

MODELS = [
    AppUser, Stock, HerdScore, HerdIndicator, DailyPrice,
    UserPortfolio, InvestorProfile, UserWatchlist, UserCashBalance, UserCashHistory, PortfolioHistory,
    SignalJournal,
]


def init_tables(engine) -> None:
    """Base.metadata.create_all로 모든 테이블을 생성한다."""
    logger.info("테이블 생성 시작...")
    Base.metadata.create_all(bind=engine)
    ensure_schema_columns(engine)
    logger.info("테이블 생성 완료")


def ensure_schema_columns(engine) -> None:
    """
    기존 DB에 새 nullable 컬럼을 보강한다.
    SQLAlchemy create_all은 이미 존재하는 테이블 컬럼을 추가하지 않으므로
    ddl-auto=validate를 쓰는 backend와 스키마를 맞추기 위해 최소 ALTER만 수행한다.
    """
    from sqlalchemy import inspect

    inspector = inspect(engine)
    if "stocks" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("stocks")}
    if "logo_url" in columns:
        return

    if engine.dialect.name == "sqlite":
        ddl = "ALTER TABLE stocks ADD COLUMN logo_url VARCHAR(300)"
    else:
        ddl = "ALTER TABLE stocks ADD COLUMN logo_url VARCHAR(300) NULL COMMENT '회사 로고 URL'"

    with engine.begin() as conn:
        conn.execute(text(ddl))
    logger.info("stocks.logo_url 컬럼 추가 완료")


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
