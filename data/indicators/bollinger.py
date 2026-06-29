"""
indicators/bollinger.py — 볼린저밴드 %B 위치 계산기

볼린저밴드는 RSI·이동평균과 달리 "변동성 대비 현재가 위치"를 측정한다.
가격이 밴드 내 어디에 위치하는지를 %B로 표현하고 역사적 백분위수로 정규화한다.

%B 해석 (raw값):
  0 미만 : 하단 밴드 이탈 (강한 공포, 과매도)
  0       : 하단 밴드 (과매도 경계)
  50      : 중간 밴드 (중립, 단기 평균 위치)
  100     : 상단 밴드 (과매수 경계)
  100 초과: 상단 밴드 이탈 (강한 과열, 과매수)

HERD와의 연관:
  - RSI가 "가격 모멘텀의 강도"를 측정한다면
  - 볼린저밴드는 "변동성 기준 군중의 쏠림 정도"를 측정한다.
  - 두 관점을 동시에 반영하면 신호 신뢰도 향상 기대.
"""

import logging

import pandas as pd
from scipy.stats import percentileofscore

logger = logging.getLogger(__name__)

# 볼린저밴드 파라미터 (변경 시 이 상수만 수정)
BB_PERIOD = 20    # 중간 밴드 단순이동평균 기간 (일봉 기준)
BB_STD    = 2.0   # 표준편차 배수 (상·하단 밴드 거리)

# 계산에 필요한 최소 일봉 수 (BB_PERIOD × 2 이상이어야 신뢰 가능)
MIN_CANDLES = BB_PERIOD * 2


def calc_bollinger_pct_b(df: pd.DataFrame) -> float:
    """
    일봉 DataFrame으로 볼린저밴드 %B 최신값을 계산해 0~100 백분위수로 반환한다.

    계산 방식:
    1. 중간 밴드 = 20일 단순이동평균 (MA20)
    2. 상단 밴드 = MA20 + 2 × 표준편차
    3. 하단 밴드 = MA20 - 2 × 표준편차
    4. %B raw = (현재가 - 하단) / (상단 - 하단) × 100
       → raw가 0~100 범위를 벗어날 수 있음 (밴드 이탈 구간)
    5. 전체 %B 시리즈를 역사적 분포로 정규화 → 0~100 백분위수 반환

    Args:
        df: 일봉 OHLCV DataFrame (Date·Open·High·Low·Close·Volume 중 Close 필수)

    Returns:
        볼린저밴드 %B 백분위수 (0~100 float)
        0에 가까울수록 하단밴드 근접 (공포), 100에 가까울수록 상단밴드 초과 (과열)

    Raises:
        ValueError: 데이터 부족으로 계산 불가 시
        KeyError: 필수 컬럼(Close) 누락 시
    """
    try:
        # Date 컬럼을 인덱스로 변환 (이미 인덱스라면 그대로 사용)
        if "Date" in df.columns:
            work = df.copy()
            work["Date"] = pd.to_datetime(work["Date"])
            work = work.set_index("Date")
        else:
            work = df

        close = work["Close"]

        if len(close) < MIN_CANDLES:
            raise ValueError(
                f"볼린저밴드 계산에 최소 {MIN_CANDLES}일 필요, 현재 {len(close)}일"
            )

        # ── 볼린저밴드 산출 ──────────────────────────────────────────────
        rolling_mean = close.rolling(window=BB_PERIOD).mean()

        # ddof=1: 표본 표준편차 (금융 시계열 관행)
        rolling_std  = close.rolling(window=BB_PERIOD).std(ddof=1)

        upper = rolling_mean + BB_STD * rolling_std
        lower = rolling_mean - BB_STD * rolling_std

        # 밴드 폭이 0이면 가격 완전 고정(거래 정지 등) → NaN 처리
        band_width = upper - lower
        pct_b_series = (
            (close - lower) / band_width.replace(0, float("nan"))
        ) * 100

        pct_b_valid = pct_b_series.dropna()

        if pct_b_valid.empty:
            raise ValueError("볼린저밴드 %B 시리즈가 비어있습니다.")

        current = float(pct_b_valid.iloc[-1])

        # ── 역사적 %B 분포 대비 백분위수 정규화 ─────────────────────────
        # raw %B는 0~100 범위를 이탈할 수 있으므로 백분위수 정규화가 필수
        result = float(percentileofscore(pct_b_valid.values, current, kind="weak"))

        logger.debug(
            f"볼린저밴드({BB_PERIOD}일, ±{BB_STD}σ): "
            f"%B raw={current:.2f} → 백분위={result:.2f}"
        )
        return result

    except ValueError as e:
        logger.error(f"[calc_bollinger_pct_b] ValueError: {e}")
        raise
    except KeyError as e:
        logger.error(f"[calc_bollinger_pct_b] 필수 컬럼 누락: {e}")
        raise
    except Exception as e:
        logger.error(f"[calc_bollinger_pct_b] 예상치 못한 오류: {type(e).__name__}: {e}")
        raise
