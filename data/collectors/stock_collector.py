"""
collectors/stock_collector.py — yfinance 주가 데이터 수집기
티커 하나를 입력받아 일봉 OHLCV 데이터를 DataFrame으로 반환한다.
"""

import time
import logging

import yfinance as yf
import pandas as pd

from config.settings import YFINANCE_PERIOD

logger = logging.getLogger(__name__)

# 재시도 설정 상수
MAX_RETRIES = 3
RETRY_DELAY_SEC = 2


def _fetch_raw(ticker: str, period: str) -> pd.DataFrame:
    """
    yfinance에서 원시 데이터를 받아오는 단일 요청 함수.
    네트워크 오류나 빈 응답은 이 함수 밖에서 처리한다.
    """
    stock = yf.Ticker(ticker)
    df = stock.history(period=period, auto_adjust=True)
    return df


def _validate(df: pd.DataFrame, ticker: str) -> None:
    """
    수집된 DataFrame이 유효한지 검증한다.
    빈 DataFrame이면 ValueError를 발생시켜 재시도 루프가 인식하도록 한다.
    """
    if df is None or df.empty:
        raise ValueError(f"[{ticker}] 빈 데이터 반환 — 존재하지 않는 티커이거나 상장 폐지 종목일 수 있습니다.")


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    yfinance 반환 컬럼을 Date, Open, High, Low, Close, Volume 순서로 정리한다.
    인덱스(날짜)를 Date 컬럼으로 변환하고 불필요한 컬럼은 제거한다.
    """
    # 날짜 인덱스를 컬럼으로 변환
    df = df.reset_index()

    # yfinance는 날짜 컬럼 이름이 'Date' 또는 'Datetime'일 수 있음
    if "Datetime" in df.columns:
        df = df.rename(columns={"Datetime": "Date"})

    # 날짜만 추출 (시분초 제거)
    df["Date"] = pd.to_datetime(df["Date"]).dt.date

    # 필요한 컬럼만 선택
    required_cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
    df = df[required_cols]

    return df


def collect(ticker: str, period: str = YFINANCE_PERIOD) -> pd.DataFrame:
    """
    지정 티커의 일봉 OHLCV 데이터를 수집해 DataFrame으로 반환한다.

    Args:
        ticker: 수집할 주식 티커 (예: "AAPL")
        period: 수집 기간 (기본값은 settings.py의 YFINANCE_PERIOD)

    Returns:
        컬럼 [Date, Open, High, Low, Close, Volume]을 가진 DataFrame

    Raises:
        RuntimeError: MAX_RETRIES 회 재시도 후에도 수집 실패 시
    """
    last_error: Exception = RuntimeError("알 수 없는 오류")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"[{ticker}] 데이터 수집 시작 (시도 {attempt}/{MAX_RETRIES}, 기간: {period})")

            df = _fetch_raw(ticker, period)
            _validate(df, ticker)
            df = _normalize_columns(df)

            logger.info(f"[{ticker}] 수집 완료 — {len(df)}행, {df['Date'].min()} ~ {df['Date'].max()}")
            return df

        except ValueError as e:
            # 빈 데이터 / 존재하지 않는 티커 — 재시도해도 의미 없으므로 즉시 실패
            logger.error(f"[{ticker}] 유효하지 않은 데이터: {e}")
            raise

        except Exception as e:
            # 네트워크 오류 등 일시적 문제 — 재시도
            last_error = e
            logger.warning(f"[{ticker}] 수집 실패 (시도 {attempt}/{MAX_RETRIES}): {e}")

            if attempt < MAX_RETRIES:
                logger.info(f"[{ticker}] {RETRY_DELAY_SEC}초 후 재시도합니다.")
                time.sleep(RETRY_DELAY_SEC)

    logger.error(f"[{ticker}] {MAX_RETRIES}회 재시도 후 최종 실패: {last_error}")
    raise RuntimeError(f"[{ticker}] 데이터 수집 실패 — {last_error}") from last_error
