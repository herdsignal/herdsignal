"""
herd/calculator.py — HERD Index 합산 계산기
5개 지표를 가중합산해 0~100 단일 점수를 산출하고 5단계를 판정한다.
티커 하나를 받으면 수집→계산→합산까지 전체 파이프라인을 자동 실행한다.
"""

import logging
from typing import TypedDict

from config.settings import HERD_WEIGHTS
from collectors.stock_collector import collect
from indicators.rsi import calc_weekly_rsi, calc_monthly_rsi
from indicators.price_position import calc_52w_position, calc_ma200_deviation
from indicators.volume import calc_volume_strength

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# HERD 5단계 경계값 (변경 시 이 상수만 수정)
# ──────────────────────────────────────────────
STAGE_BOUNDARIES = [
    (0,   20,  "Herd Flee"),     # 극단적 공포 — 매수 타이밍
    (20,  40,  "Herd Scatter"),  # 약한 공포
    (40,  60,  "Herd Calm"),     # 중립
    (60,  80,  "Herd Drift"),    # 약한 탐욕
    (80,  100, "Herd Rush"),     # 극단적 탐욕 — 익절 타이밍
]


# ──────────────────────────────────────────────
# 반환 타입 정의
# ──────────────────────────────────────────────
class IndicatorValues(TypedDict):
    weekly_rsi:      float
    monthly_rsi:     float
    position_52w:    float
    ma200_deviation: float
    volume_strength: float


class HerdResult(TypedDict):
    ticker:     str
    score:      float
    stage:      str
    indicators: IndicatorValues


def get_stage(score: float) -> str:
    """
    HERD 점수를 입력받아 5단계 중 하나를 반환한다.
    경계값(20, 40, 60, 80)은 상위 단계에 포함된다.
    """
    for lower, upper, label in STAGE_BOUNDARIES:
        if lower <= score < upper:
            return label
    # 정확히 100.0일 경우 최상위 단계 반환
    return STAGE_BOUNDARIES[-1][2]


def calc_herd_score(indicators: IndicatorValues) -> float:
    """
    5개 지표값을 HERD_WEIGHTS로 가중합산해 HERD 점수를 반환한다.

    Args:
        indicators: 5개 지표 딕셔너리

    Returns:
        HERD 점수 (0~100 float)
    """
    # settings.py의 키 이름과 indicators 딕셔너리 키를 매핑
    key_map = {
        "monthly_rsi":     "monthly_rsi",
        "weekly_rsi":      "weekly_rsi",
        "52w_position":    "position_52w",
        "ma200_deviation": "ma200_deviation",
        "volume_strength": "volume_strength",
    }

    score = 0.0
    for settings_key, indicator_key in key_map.items():
        weight = HERD_WEIGHTS[settings_key]
        value  = indicators[indicator_key]
        score += weight * value

    return round(float(max(0.0, min(100.0, score))), 2)


def run(ticker: str) -> HerdResult:
    """
    티커 하나를 입력받아 전체 파이프라인을 실행하고 HERD 결과를 반환한다.

    파이프라인: 데이터 수집 → 5개 지표 계산 → 가중합산 → 단계 판정

    Args:
        ticker: 주식 티커 (예: "AAPL")

    Returns:
        HerdResult 딕셔너리

    Raises:
        RuntimeError: 데이터 수집 또는 지표 계산 실패 시
    """
    logger.info(f"[{ticker}] HERD Index 계산 시작")

    # 1. 일봉 데이터 수집
    try:
        df = collect(ticker)
    except Exception as e:
        logger.error(f"[{ticker}] 데이터 수집 실패: {e}")
        raise RuntimeError(f"[{ticker}] 데이터 수집 실패") from e

    # 2. 5개 지표 계산 — 각각 개별 예외처리 후 한 번에 실패 판단
    indicator_funcs = {
        "weekly_rsi":      lambda: calc_weekly_rsi(df),
        "monthly_rsi":     lambda: calc_monthly_rsi(df),
        "position_52w":    lambda: calc_52w_position(df),
        "ma200_deviation": lambda: calc_ma200_deviation(df),
        "volume_strength": lambda: calc_volume_strength(df),
    }

    values: dict[str, float] = {}
    failed: list[str] = []

    for name, func in indicator_funcs.items():
        try:
            values[name] = func()
        except Exception as e:
            logger.error(f"[{ticker}] 지표 계산 실패 — {name}: {e}")
            failed.append(name)

    # 하나라도 실패하면 전체 실패 처리
    if failed:
        raise RuntimeError(
            f"[{ticker}] 지표 계산 실패 ({', '.join(failed)}) — HERD Index 산출 불가"
        )

    indicators = IndicatorValues(
        weekly_rsi      = values["weekly_rsi"],
        monthly_rsi     = values["monthly_rsi"],
        position_52w    = values["position_52w"],
        ma200_deviation = values["ma200_deviation"],
        volume_strength = values["volume_strength"],
    )

    # 3. 가중합산 및 단계 판정
    score = calc_herd_score(indicators)
    stage = get_stage(score)

    result = HerdResult(
        ticker     = ticker.upper(),
        score      = score,
        stage      = stage,
        indicators = indicators,
    )

    logger.info(f"[{ticker}] HERD Index = {score:.2f} ({stage})")
    return result
