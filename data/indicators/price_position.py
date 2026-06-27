"""
indicators/price_position.py — 가격 위치 지표 계산기
52주 고저 위치와 200일 이동평균 이격도를 산출한다.
"""

import logging

import pandas as pd

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
    """
    if len(df) < TRADING_DAYS_1Y:
        raise ValueError(
            f"52주 위치 계산에 최소 {TRADING_DAYS_1Y}거래일 필요, 현재 {len(df)}일"
        )

    # 최근 252거래일 기준으로 고점/저점 산출
    recent = df.tail(TRADING_DAYS_1Y)
    high_52w = float(recent["High"].max())
    low_52w = float(recent["Low"].min())
    current = _get_latest_close(df)

    price_range = high_52w - low_52w
    if price_range == 0:
        raise ValueError("52주 고점과 저점이 동일합니다 — 계산 불가 (거래 정지 가능성)")

    raw = (current - low_52w) / price_range * 100.0
    result = float(max(0.0, min(100.0, raw)))

    logger.debug(f"52주 고저 위치: {result:.2f} (현재가 {current:.2f}, 저 {low_52w:.2f}, 고 {high_52w:.2f})")
    return result


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
    """
    if len(df) < MA_PERIOD:
        raise ValueError(
            f"MA{MA_PERIOD} 계산에 최소 {MA_PERIOD}거래일 필요, 현재 {len(df)}일"
        )

    ma200 = float(df["Close"].rolling(window=MA_PERIOD).mean().iloc[-1])

    if ma200 == 0:
        raise ValueError("MA200이 0입니다 — 계산 불가")

    current = _get_latest_close(df)

    # 원시 이격도 (%)
    raw_deviation = (current - ma200) / ma200 * 100.0

    # [-CLIP, +CLIP] 범위로 클리핑 후 [0, 100]으로 선형 변환
    clipped = max(-DEVIATION_CLIP, min(DEVIATION_CLIP, raw_deviation))
    result = (clipped + DEVIATION_CLIP) / (2 * DEVIATION_CLIP) * 100.0

    logger.debug(
        f"MA{MA_PERIOD} 이격도: raw={raw_deviation:.2f}%, 정규화={result:.2f} "
        f"(현재가 {current:.2f}, MA{MA_PERIOD} {ma200:.2f})"
    )
    return result
