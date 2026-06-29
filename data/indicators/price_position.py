"""
indicators/price_position.py — 가격 위치 지표 계산기
52주 고저 위치와 200일 이동평균 이격도를 산출한다.
"""

import logging

import pandas as pd
from scipy.stats import percentileofscore

logger = logging.getLogger(__name__)

# 52주 고저 위치 계산에 사용할 거래일 수 (1년 ≈ 252 거래일)
TRADING_DAYS_1Y = 252

# 이격도 계산에 사용할 이동평균 기간
MA_PERIOD = 200

# 이격도 정규화에 사용할 클리핑 범위 (±50% 이상은 극단값으로 처리)
# 실제 시장에서 MA200 대비 ±50% 이상 이탈은 매우 드문 상황임
DEVIATION_CLIP = 50.0


def _get_latest_close(df: pd.DataFrame) -> float:
    """
    DataFrame에서 가장 최근 종가를 반환한다.
    """
    return float(df["Close"].iloc[-1])


def calc_52w_position(df: pd.DataFrame) -> float:
    """
    52주 고저 위치를 계산해 반환한다.
    현재가가 지난 1년의 가격 범위 내 어디에 위치하는지를 0~100으로 표현한다.
    0에 가까울수록 52주 저점, 100에 가까울수록 52주 고점.

    공식: (현재가 - 52주저) / (52주고 - 52주저) × 100

    Args:
        df: 일봉 OHLCV DataFrame (Date, Open, High, Low, Close, Volume)

    Returns:
        52주 고저 위치 (0~100 float)

    Raises:
        ValueError: 1년치 데이터 부족 또는 52주 고저 차이가 0인 경우
        KeyError: 필수 컬럼(High/Low/Close 등) 누락 시
    """
    try:
        if len(df) < TRADING_DAYS_1Y:
            raise ValueError(
                f"52주 위치 계산에 최소 {TRADING_DAYS_1Y}거래일 필요, 현재 {len(df)}일"
            )

        # 전체 기간에 걸쳐 매일의 52주 고저 위치 비율 시리즈 산출
        rolling_high = df["High"].rolling(window=TRADING_DAYS_1Y).max()
        rolling_low  = df["Low"].rolling(window=TRADING_DAYS_1Y).min()
        price_range  = rolling_high - rolling_low

        # 범위가 0인 시점(거래 정지 등) 제거
        valid = price_range[price_range > 0]
        position_series = (
            (df["Close"][valid.index] - rolling_low[valid.index]) / price_range[valid.index] * 100.0
        ).dropna()

        if position_series.empty:
            raise ValueError("52주 고저 위치 시리즈가 비어있습니다.")

        current = float(position_series.iloc[-1])
        result  = float(percentileofscore(position_series.values, current, kind="weak"))

        logger.debug(f"52주 고저 위치: raw={current:.2f} → 백분위={result:.2f}")
        return result

    except ValueError as e:
        logger.error(f"[calc_52w_position] ValueError: {e}")
        raise
    except KeyError as e:
        logger.error(f"[calc_52w_position] 필수 컬럼 누락: {e}")
        raise
    except Exception as e:
        logger.error(f"[calc_52w_position] 예상치 못한 오류: {type(e).__name__}: {e}")
        raise


def calc_ma200_deviation(df: pd.DataFrame) -> float:
    """
    200일 이동평균 이격도를 계산해 0~100으로 정규화해 반환한다.

    원시 이격도 공식: (현재가 - MA200) / MA200 × 100
    → 음수(MA200 아래)~양수(MA200 위) 범위를 가짐

    정규화:
    - ±DEVIATION_CLIP(50%) 범위로 클리핑
    - [-50, +50] → [0, 100]으로 선형 변환
    → 50이 MA200과 동가, 100이 MA200 대비 +50% 위

    Args:
        df: 일봉 OHLCV DataFrame (Date, Open, High, Low, Close, Volume)

    Returns:
        MA200 이격도 정규화값 (0~100 float)

    Raises:
        ValueError: MA200 계산에 필요한 데이터 부족 시
        KeyError: 필수 컬럼(Close 등) 누락 시
    """
    try:
        if len(df) < MA_PERIOD:
            raise ValueError(
                f"MA{MA_PERIOD} 계산에 최소 {MA_PERIOD}거래일 필요, 현재 {len(df)}일"
            )

        close    = df["Close"]
        ma200    = close.rolling(window=MA_PERIOD).mean()

        # MA200이 존재하는 구간의 전체 이격도 시리즈 산출
        valid_ma = ma200[ma200 > 0].dropna()
        deviation_series = (
            (close[valid_ma.index] - valid_ma) / valid_ma * 100.0
        ).dropna()

        if deviation_series.empty:
            raise ValueError("MA200 이격도 시리즈가 비어있습니다.")

        current = float(deviation_series.iloc[-1])
        result  = float(percentileofscore(deviation_series.values, current, kind="weak"))

        logger.debug(
            f"MA{MA_PERIOD} 이격도: raw={current:.2f}% → 백분위={result:.2f}"
        )
        return result

    except ValueError as e:
        logger.error(f"[calc_ma200_deviation] ValueError: {e}")
        raise
    except KeyError as e:
        logger.error(f"[calc_ma200_deviation] 필수 컬럼 누락: {e}")
        raise
    except Exception as e:
        logger.error(f"[calc_ma200_deviation] 예상치 못한 오류: {type(e).__name__}: {e}")
        raise
