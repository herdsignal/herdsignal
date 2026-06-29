"""
indicators/ma200_weekly.py — 200주 이동평균 위치 계산기

일봉 DataFrame을 주봉으로 리샘플링 후 200주 단순 이동평균(SMA)을 산출하고,
현재가 / MA200W 비율의 역사적 백분위수를 0~100으로 반환한다.

해석:
  0~20  : 현재가가 200주 MA 하회/근접 → 장기 저점 구간 (멍거 전략 매수 신호)
  80~100: 현재가가 200주 MA 대비 크게 상회 → 장기 과열 구간

IONQ처럼 상장 기간이 짧은 종목은 가용 주봉 수로 MA 기간을 자동 조정한다.
(예: 100주 데이터 → 99주 MA로 계산)
"""

import logging

import pandas as pd
from scipy.stats import percentileofscore

logger = logging.getLogger(__name__)

# 200주 이동평균 기간 (주봉 기준, 약 4년)
MA_WEEKLY_PERIOD = 200

# 계산에 필요한 최소 주봉 수
# (이보다 적으면 MA 의미가 없어 ValueError 발생)
MIN_WEEKLY_CANDLES = 26  # 최소 반년


def _resample_to_weekly_close(df: pd.DataFrame) -> pd.Series:
    """
    일봉 DataFrame을 주봉 종가 시리즈로 리샘플링한다.
    Date 컬럼이 있으면 인덱스로 변환 후 주봉("W") 기준 마지막 값 추출.
    """
    if "Date" in df.columns:
        df = df.copy()
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")

    # "W" = 주봉 마지막 거래일 종가
    weekly_close = df["Close"].resample("W").last().dropna()
    return weekly_close


def calc_ma200_weekly(df: pd.DataFrame) -> float:
    """
    200주 이동평균 대비 현재가 위치를 계산해 0~100으로 정규화한다.

    계산 방식:
    1. 일봉 → 주봉 리샘플링 (종가 기준)
    2. 가용 데이터가 200주 미만이면 실제 가용 주봉 수로 MA 기간 자동 조정
    3. 현재가 / MA 비율 시리즈를 전체 기간에 걸쳐 산출
    4. 최신 비율을 역사적 분포에서 백분위수로 변환해 반환

    Args:
        df: 일봉 OHLCV DataFrame (Date, Open, High, Low, Close, Volume)

    Returns:
        200주 MA 위치 정규화값 (0~100 float)

    Raises:
        ValueError: 최소 주봉 데이터(26주) 부족 시
        KeyError: 필수 컬럼(Close) 누락 시
    """
    try:
        weekly_close = _resample_to_weekly_close(df)

        if len(weekly_close) < MIN_WEEKLY_CANDLES:
            raise ValueError(
                f"200주 MA 계산에 최소 {MIN_WEEKLY_CANDLES}주 필요, "
                f"현재 {len(weekly_close)}주"
            )

        # 데이터가 200주 미만이면 가용 기간으로 자동 조정
        actual_period = min(MA_WEEKLY_PERIOD, len(weekly_close) - 1)
        if actual_period < MA_WEEKLY_PERIOD:
            logger.warning(
                f"200주 데이터 부족 — {actual_period}주 MA로 자동 조정 "
                f"(보유 주봉: {len(weekly_close)}주)"
            )

        # 전체 기간의 현재가 / MA 비율 시리즈 산출
        ma_series = weekly_close.rolling(window=actual_period).mean()
        valid_ma   = ma_series.dropna()

        if valid_ma.empty:
            raise ValueError("200주 MA 시리즈가 비어있습니다.")

        # MA가 0인 구간(거래 정지 등) 제외
        ratio_series = (
            weekly_close[valid_ma.index] / valid_ma.replace(0, float("nan"))
        ).dropna()

        if ratio_series.empty:
            raise ValueError("200주 MA 비율 시리즈가 비어있습니다.")

        current_ratio = float(ratio_series.iloc[-1])
        result = float(
            percentileofscore(ratio_series.values, current_ratio, kind="weak")
        )

        logger.debug(
            f"200주 MA({actual_period}주): "
            f"현재 비율={current_ratio:.4f} → 백분위={result:.2f}"
        )
        return result

    except ValueError as e:
        logger.error(f"[calc_ma200_weekly] ValueError: {e}")
        raise
    except KeyError as e:
        logger.error(f"[calc_ma200_weekly] 필수 컬럼 누락: {e}")
        raise
    except Exception as e:
        logger.error(f"[calc_ma200_weekly] 예상치 못한 오류: {type(e).__name__}: {e}")
        raise
