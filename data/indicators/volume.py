"""
indicators/volume.py — 거래량 강도 계산기
최근 5일 평균 거래량을 과거 20일 평균 거래량으로 나눈 비율을
종목별 역사적 분포 기준으로 0~100 정규화해 반환한다.
"""

import logging

import pandas as pd
from scipy.stats import percentileofscore

logger = logging.getLogger(__name__)

# 단기 평균 거래량 계산 기간 (최근 거래량 활성도 측정)
SHORT_WINDOW = 5

# 장기 평균 거래량 계산 기간 (기준선 역할)
LONG_WINDOW = 20

# 역사적 백분위 계산에 사용할 최소 데이터 수
# (비율 시리즈를 만들려면 LONG_WINDOW 이후부터 값이 생김)
MIN_ROWS = LONG_WINDOW + SHORT_WINDOW

# (이전 선형 클리핑 방식에서 percentileofscore 방식으로 변경됨)


def _calc_volume_ratio_series(volume: pd.Series) -> pd.Series:
    """
    전체 거래량 시리즈에서 단기/장기 평균 비율을 계산한다.
    반환값은 NaN이 앞에 붙은 전체 길이의 시리즈.
    """
    short_avg = volume.rolling(window=SHORT_WINDOW).mean()
    long_avg = volume.rolling(window=LONG_WINDOW).mean()

    # 장기 평균이 0이면 해당 시점을 NaN 처리 (거래 정지 구간 등)
    ratio = short_avg / long_avg.replace(0, float("nan"))
    return ratio


def calc_volume_strength(df: pd.DataFrame) -> float:
    """
    거래량 강도를 계산해 0~100으로 정규화해 반환한다.

    정규화 방식:
    - 전체 기간의 거래량 비율(단기/장기) 시리즈를 산출한다.
    - 역사적 분포의 하위 2%~상위 98% 범위를 기준 구간으로 설정한다.
    - 최신 비율이 이 범위 내 어디에 위치하는지를 0~100으로 선형 변환한다.
    - 극단값(범위 초과)은 0 또는 100으로 클리핑한다.

    Args:
        df: 일봉 OHLCV DataFrame (Date, Open, High, Low, Close, Volume)

    Returns:
        거래량 강도 정규화값 (0~100 float)

    Raises:
        ValueError: 데이터 부족 또는 거래량 데이터 없음
        KeyError: 필수 컬럼(Volume 등) 누락 시
    """
    try:
        if len(df) < MIN_ROWS:
            raise ValueError(
                f"거래량 강도 계산에 최소 {MIN_ROWS}거래일 필요, 현재 {len(df)}일"
            )

        volume = df["Volume"].copy()

        # 거래량이 전부 0이면 거래 정지 종목으로 판단
        if volume.sum() == 0:
            raise ValueError("거래량 데이터가 모두 0입니다 — 거래 정지 종목일 수 있습니다.")

        ratio_series = _calc_volume_ratio_series(volume)

        valid_ratios = ratio_series.dropna()
        if valid_ratios.empty:
            raise ValueError("유효한 거래량 비율 데이터가 없습니다.")

        current_ratio = float(valid_ratios.iloc[-1])
        result = float(percentileofscore(valid_ratios.values, current_ratio, kind="weak"))

        logger.debug(f"거래량 비율: 현재={current_ratio:.4f} → 백분위={result:.2f}")
        return result

    except ValueError as e:
        logger.error(f"[calc_volume_strength] ValueError: {e}")
        raise
    except KeyError as e:
        logger.error(f"[calc_volume_strength] 필수 컬럼 누락: {e}")
        raise
    except Exception as e:
        logger.error(f"[calc_volume_strength] 예상치 못한 오류: {type(e).__name__}: {e}")
        raise
