"""
indicators/rsi.py — 주봉 / 월봉 RSI 계산기
일봉 DataFrame을 리샘플링해 RSI를 산출하고 최신값 하나를 반환한다.
"""

import logging

import pandas as pd
import pandas_ta as ta
from scipy.stats import percentileofscore

logger = logging.getLogger(__name__)

# RSI 기본 기간 (변경 시 이 상수만 수정)
RSI_PERIOD = 14

# RSI 계산에 필요한 최소 캔들 수 (RSI 기간 × 2 이상이어야 신뢰 가능)
MIN_CANDLES = RSI_PERIOD * 2


def _resample_to_ohlcv(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """
    일봉 DataFrame을 지정 주기(W=주봉, ME=월봉)로 리샘플링한다.
    Close 기준 RSI를 구하기 위해 OHLCV 집계 방식을 적용한다.
    """
    # Date 컬럼을 인덱스로 변환 (이미 인덱스라면 그대로 사용)
    if "Date" in df.columns:
        df = df.copy()
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")

    resampled = df.resample(freq).agg({
        "Open":   "first",
        "High":   "max",
        "Low":    "min",
        "Close":  "last",
        "Volume": "sum",
    }).dropna()  # 아직 마감되지 않은 부분 캔들 제거

    return resampled


def _calc_rsi(series: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """
    pandas_ta를 이용해 Close 시리즈의 RSI를 계산한다.
    """
    rsi = ta.rsi(series, length=period)
    return rsi


def _percentile_normalize(series_values: pd.Series, current: float) -> float:
    """
    현재값이 역사적 분포에서 몇 번째 백분위에 있는지 반환한다.
    kind='weak': 현재값 이하인 값의 비율 (0~100).
    """
    return float(percentileofscore(series_values, current, kind="weak"))


def calc_weekly_rsi(df: pd.DataFrame, period: int = RSI_PERIOD) -> float:
    """
    일봉 DataFrame으로 주봉 RSI 최신값을 계산해 반환한다.

    Args:
        df: 일봉 OHLCV DataFrame (Date, Open, High, Low, Close, Volume)
        period: RSI 기간 (기본값 14)

    Returns:
        주봉 RSI 최신값 (0~100 float)

    Raises:
        ValueError: 데이터 부족으로 RSI 계산 불가 시
    """
    weekly = _resample_to_ohlcv(df, freq="W")

    if len(weekly) < MIN_CANDLES:
        raise ValueError(
            f"주봉 데이터 부족 — RSI 계산에 최소 {MIN_CANDLES}주 필요, 현재 {len(weekly)}주"
        )

    rsi_series = _calc_rsi(weekly["Close"], period)

    # 유효한 마지막 값 추출 (NaN 제거 후)
    rsi_valid = rsi_series.dropna()
    if rsi_valid.empty:
        raise ValueError("주봉 RSI 계산 결과가 모두 NaN입니다.")

    current = float(rsi_valid.iloc[-1])
    result = _percentile_normalize(rsi_valid.values, current)
    logger.debug(f"주봉 RSI({period}) raw={current:.2f} → 백분위={result:.2f}")
    return result


def calc_monthly_rsi(df: pd.DataFrame, period: int = RSI_PERIOD) -> float:
    """
    일봉 DataFrame으로 월봉 RSI 최신값을 계산해 반환한다.

    Args:
        df: 일봉 OHLCV DataFrame (Date, Open, High, Low, Close, Volume)
        period: RSI 기간 (기본값 14)

    Returns:
        월봉 RSI 최신값 (0~100 float)

    Raises:
        ValueError: 데이터 부족으로 RSI 계산 불가 시
    """
    # ME: Month End (pandas 2.2+ 권장 별칭, 구버전의 'M'을 대체)
    monthly = _resample_to_ohlcv(df, freq="ME")

    if len(monthly) < MIN_CANDLES:
        raise ValueError(
            f"월봉 데이터 부족 — RSI 계산에 최소 {MIN_CANDLES}개월 필요, 현재 {len(monthly)}개월"
        )

    rsi_series = _calc_rsi(monthly["Close"], period)

    rsi_valid = rsi_series.dropna()
    if rsi_valid.empty:
        raise ValueError("월봉 RSI 계산 결과가 모두 NaN입니다.")

    current = float(rsi_valid.iloc[-1])
    result = _percentile_normalize(rsi_valid.values, current)
    logger.debug(f"월봉 RSI({period}) raw={current:.2f} → 백분위={result:.2f}")
    return result
