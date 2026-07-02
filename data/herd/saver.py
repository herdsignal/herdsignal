"""
herd/saver.py — HERD 계산 결과를 MariaDB에 저장
calculator.run() 반환값과 collect() DataFrame을 받아
4개 테이블(stocks / herd_scores / herd_indicators / daily_prices)에 UPSERT한다.
"""

import logging
from datetime import date, datetime

import pandas as pd
from sqlalchemy.exc import SQLAlchemyError

from config.database import create_db_engine, get_session_factory
from config.settings import HERD_THRESHOLDS
# init_db.py의 ORM 모델 재사용 — 동일한 Base를 공유하므로 metadata 충돌 없음
from init_db import DailyPrice, HerdIndicator, HerdScore, Stock

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 모듈 로드 시 엔진·세션 팩토리 1회 초기화
# ──────────────────────────────────────────────
_engine         = create_db_engine()
_SessionFactory = get_session_factory(_engine)


# ──────────────────────────────────────────────
# 내부 헬퍼
# ──────────────────────────────────────────────
def _now() -> datetime:
    """현재 UTC 시각을 반환한다."""
    return datetime.utcnow()


def _derive_signal(score: float) -> str:
    """
    HERD 점수로 단순 매매 신호를 파생한다.
    settings.py의 HERD_THRESHOLDS를 기준으로 판단.
    """
    rush_t = HERD_THRESHOLDS["rush"]   # 75
    flee_t = HERD_THRESHOLDS["flee"]   # 15

    if score >= rush_t:
        return "SELL"     # Rush: 익절 신호
    if score <= flee_t:
        return "BUY"      # Flee: 매수 신호
    if score >= 60.0:
        return "REDUCE"   # Drift: 부분 익절 신호
    if score <= 40.0:
        return "ADD"      # Scatter: 부분 매수 신호
    return "HOLD"         # Calm: 보유 유지


def _upsert_stock(session, ticker: str) -> None:
    """
    stocks 테이블에 종목이 없으면 INSERT, 있으면 updated_at만 갱신.
    name / sector / market_cap_category는 별도 메타데이터 수집 단계에서 채울 예정.
    """
    obj = session.query(Stock).filter_by(ticker=ticker).first()
    now = _now()

    if obj is None:
        session.add(Stock(
            ticker     = ticker,
            is_active  = True,
            created_at = now,
            updated_at = now,
        ))
        logger.info(f"[{ticker}] stocks INSERT")
    else:
        # 종목명 등 메타정보는 건드리지 않고 갱신 시각만 업데이트
        obj.updated_at = now
        logger.debug(f"[{ticker}] stocks updated_at 갱신")


def _upsert_herd_score(session, ticker: str,
                       score: float, stage: str, score_date: date) -> None:
    """
    herd_scores 테이블에 (ticker, score_date) 기준으로 UPSERT.
    같은 날 재실행하면 점수·단계·신호를 덮어씀.
    """
    signal = _derive_signal(score)
    obj    = (session.query(HerdScore)
              .filter_by(ticker=ticker, score_date=score_date)
              .first())
    now = _now()

    if obj is None:
        session.add(HerdScore(
            ticker     = ticker,
            score_date = score_date,
            herd_score = round(score, 2),
            herd_stage = stage,
            signal     = signal,
            created_at = now,
        ))
        logger.info(
            f"[{ticker}] herd_scores INSERT  "
            f"date={score_date}  score={score:.2f}  stage={stage}  signal={signal}"
        )
    else:
        obj.herd_score = round(score, 2)
        obj.herd_stage = stage
        obj.signal     = signal
        logger.info(
            f"[{ticker}] herd_scores UPDATE  "
            f"date={score_date}  score={score:.2f}  stage={stage}  signal={signal}"
        )


def _upsert_herd_indicators(session, ticker: str,
                             indicators: dict, score_date: date) -> None:
    """
    herd_indicators 테이블에 (ticker, score_date) 기준으로 UPSERT.
    HERD 지표값을 소수점 2자리로 반올림해 저장.
    """
    obj = (session.query(HerdIndicator)
           .filter_by(ticker=ticker, score_date=score_date)
           .first())
    now = _now()

    # indicators 딕셔너리 → 컬럼 매핑
    fields = {
        "weekly_rsi"     : round(float(indicators["weekly_rsi"]),      2),
        "monthly_rsi"    : round(float(indicators["monthly_rsi"]),     2),
        "position_52w"   : round(float(indicators["position_52w"]),    2),
        "ma200_deviation": round(float(indicators["ma200_deviation"]), 2),
        "volume_strength": round(float(indicators["volume_strength"]), 2),
        "ma200_weekly"   : round(float(indicators["ma200_weekly"]),    2),
    }

    if obj is None:
        session.add(HerdIndicator(
            ticker     = ticker,
            score_date = score_date,
            created_at = now,
            **fields,
        ))
        logger.info(f"[{ticker}] herd_indicators INSERT  date={score_date}  {fields}")
    else:
        for col, val in fields.items():
            setattr(obj, col, val)
        logger.info(f"[{ticker}] herd_indicators UPDATE  date={score_date}")


def _upsert_daily_price(session, ticker: str, df: pd.DataFrame) -> None:
    """
    daily_prices 테이블에 DataFrame 마지막 행(최신 거래일)을 UPSERT.
    Date가 컬럼인 경우와 인덱스인 경우 모두 처리.
    """
    last = df.iloc[-1]

    # Date 처리 — 컬럼 또는 DatetimeIndex 양쪽 대응
    if "Date" in df.columns:
        price_date = pd.Timestamp(last["Date"]).date()
    else:
        price_date = pd.Timestamp(df.index[-1]).date()

    obj = (session.query(DailyPrice)
           .filter_by(ticker=ticker, price_date=price_date)
           .first())
    now = _now()

    fields = {
        "open_price" : round(float(last["Open"]),  4),
        "high_price" : round(float(last["High"]),  4),
        "low_price"  : round(float(last["Low"]),   4),
        "close_price": round(float(last["Close"]), 4),
        "volume"     : int(last["Volume"]),
    }

    if obj is None:
        session.add(DailyPrice(
            ticker     = ticker,
            price_date = price_date,
            created_at = now,
            **fields,
        ))
        logger.info(
            f"[{ticker}] daily_prices INSERT  "
            f"date={price_date}  close={fields['close_price']}"
        )
    else:
        for col, val in fields.items():
            setattr(obj, col, val)
        logger.info(
            f"[{ticker}] daily_prices UPDATE  "
            f"date={price_date}  close={fields['close_price']}"
        )


# ──────────────────────────────────────────────
# 공개 API
# ──────────────────────────────────────────────
def save_herd_result(ticker: str, herd_result: dict, df: pd.DataFrame) -> bool:
    """
    HERD 계산 결과를 4개 테이블에 트랜잭션으로 저장한다.
    한 테이블이라도 실패하면 전체 롤백.

    Args:
        ticker:      티커 심볼 (예: "AAPL")
        herd_result: calculator.run() 반환값 (HerdResult TypedDict)
        df:          stock_collector.collect() 반환 DataFrame

    Returns:
        저장 성공 여부 (True / False)
    """
    score_date = date.today()
    logger.info(f"[{ticker}] ── DB 저장 시작  날짜={score_date} ──")

    with _SessionFactory() as session:
        try:
            _upsert_stock(session, ticker)
            _upsert_herd_score(
                session, ticker,
                herd_result["score"],
                herd_result["stage"],
                score_date,
            )
            _upsert_herd_indicators(
                session, ticker,
                herd_result["indicators"],
                score_date,
            )
            _upsert_daily_price(session, ticker, df)

            session.commit()
            logger.info(f"[{ticker}] ── DB 저장 완료 ──")
            return True

        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"[{ticker}] DB 저장 실패 — 롤백 처리: {e}")
            return False


def save_herd_for_date(ticker: str, herd_result: dict, score_date: date) -> bool:
    """
    백필용 — score_date를 외부에서 지정해 herd_scores + herd_indicators에 UPSERT.
    daily_prices는 운영 스케줄러가 관리하므로 포함하지 않는다.

    Args:
        ticker:      티커 심볼 (예: "SPY")
        herd_result: calculator 결과 딕셔너리 (score / stage / indicators)
        score_date:  저장할 날짜

    Returns:
        저장 성공 여부 (True / False)
    """
    logger.debug(f"[{ticker}] 백필 저장  날짜={score_date}")

    with _SessionFactory() as session:
        try:
            _upsert_stock(session, ticker)
            _upsert_herd_score(
                session, ticker,
                herd_result["score"],
                herd_result["stage"],
                score_date,
            )
            _upsert_herd_indicators(
                session, ticker,
                herd_result["indicators"],
                score_date,
            )
            session.commit()
            return True

        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"[{ticker}] 백필 저장 실패 — 롤백 처리 ({score_date}): {e}")
            return False
