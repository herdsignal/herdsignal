"""
collectors/price_collector.py — yfinance 실시간 현재가 조회

yfinance의 무료 티어는 약 15분 지연 데이터를 제공한다.
여러 종목을 한번에 다운로드해 API 호출 횟수를 최소화한다.
"""

import logging
import sys
from datetime import time
from pathlib import Path

import pandas as pd
import yfinance as yf

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

logger = logging.getLogger(__name__)


def _extract_close_frame(df: pd.DataFrame, tickers: list) -> pd.DataFrame:
    """yf.download 결과에서 Close 컬럼만 ticker별 DataFrame으로 정규화한다."""
    if df.empty:
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        if "Close" in df.columns.get_level_values(0):
            close = df["Close"]
        elif "Close" in df.columns.get_level_values(1):
            close = df.xs("Close", axis=1, level=1)
        else:
            return pd.DataFrame()
    elif "Close" in df.columns:
        close = df["Close"]
    else:
        return pd.DataFrame()

    if isinstance(close, pd.Series):
        return pd.DataFrame({tickers[0]: close})
    return close


def _latest_regular_close(daily_closes: pd.Series, current_price: float, latest_ts) -> float:
    """
    일일 등락률 기준이 되는 직전 정규장 종가를 반환한다.

    yfinance daily 데이터는 장중/장후 갱신 타이밍이 달라질 수 있다.
    - 프리장/장중: daily 최신값을 직전 정규장 종가로 사용
    - 정규장 마감 후 daily 최신값이 현재가와 같은 날짜로 갱신된 경우: 한 칸 이전 종가 사용
    """
    closes = daily_closes.dropna()
    if closes.empty:
        return current_price

    prev_close = float(closes.iloc[-1])
    if len(closes) < 2 or latest_ts is None:
        return prev_close

    try:
        latest = pd.Timestamp(latest_ts)
        if latest.tzinfo is not None:
            latest = latest.tz_convert("America/New_York")

        latest_date = latest.date()
        latest_time = latest.time()
        daily_last_date = pd.Timestamp(closes.index[-1]).date()

        if (
            latest_date == daily_last_date
            and latest_time >= time(16, 0)
            and abs(current_price - prev_close) / prev_close < 0.001
        ):
            return float(closes.iloc[-2])
    except Exception:
        return prev_close

    return prev_close


def get_current_prices(tickers: list) -> dict:
    """
    여러 종목의 현재가(15분 지연)를 yfinance로 일괄 조회한다.

    단일·다중 종목 모두 yf.download 한 번으로 처리.
    실패한 종목은 None으로 반환해 호출자가 제외 여부를 결정.

    Args:
        tickers: 종목 티커 목록 (예: ["NVDA", "AAPL"])

    Returns:
        {
            "NVDA": {
                "price":      float,  # 최신 종가 (15분 지연)
                "prev_close": float,  # 전일 종가
                "change_pct": float,  # 전일 대비 등락률 (%)
            },
            "AAPL": None,  # 조회 실패 시 None
            ...
        }
    """
    if not tickers:
        return {}

    # 결과 초기화 — 조회 실패 종목은 None 유지
    result: dict = {ticker: None for ticker in tickers}

    try:
        # 1분봉 + prepost=True로 프리장/애프터장 가격까지 포함한다.
        # 일봉은 직전 정규장 종가(prev_close) 기준 계산에만 사용한다.
        intraday_df = yf.download(
            tickers=tickers,
            period="5d",
            interval="1m",
            prepost=True,
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        daily_df = yf.download(
            tickers=tickers,
            period="7d",
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=True,
        )

        if intraday_df.empty and daily_df.empty:
            logger.warning(f"[price_collector] yfinance 반환 데이터 없음: {tickers}")
            return result

        intraday_close_df = _extract_close_frame(intraday_df, tickers)
        daily_close_df = _extract_close_frame(daily_df, tickers)

        for ticker in tickers:
            try:
                current_series = (
                    intraday_close_df[ticker].dropna()
                    if ticker in intraday_close_df.columns
                    else pd.Series(dtype=float)
                )
                daily_series = (
                    daily_close_df[ticker].dropna()
                    if ticker in daily_close_df.columns
                    else pd.Series(dtype=float)
                )

                if current_series.empty and daily_series.empty:
                    logger.warning(f"[price_collector][{ticker}] 컬럼 없음")
                    continue

                # 프리장/장중이면 intraday 최신값, 실패 시 일봉 최신값으로 폴백
                if not current_series.empty:
                    current_price = float(current_series.iloc[-1])
                    latest_ts = current_series.index[-1]
                else:
                    current_price = float(daily_series.iloc[-1])
                    latest_ts = daily_series.index[-1]

                prev_close = _latest_regular_close(daily_series, current_price, latest_ts)
                change_pct = (
                    (current_price - prev_close) / prev_close * 100
                    if prev_close > 0 else 0.0
                )

                result[ticker] = {
                    "price":      round(current_price, 4),
                    "prev_close": round(prev_close, 4),
                    "change_pct": round(change_pct, 4),
                }
                logger.info(
                    f"[price_collector][{ticker}] "
                    f"현재가=${current_price:.2f}  전일=${prev_close:.2f}  "
                    f"등락={change_pct:+.2f}%"
                )

            except Exception as e:
                logger.error(f"[price_collector][{ticker}] 가격 파싱 실패: {e}")
                result[ticker] = None

    except Exception as e:
        logger.error(f"[price_collector] yfinance 일괄 조회 실패: {e}", exc_info=True)

    return result
