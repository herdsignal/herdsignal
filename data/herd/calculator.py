"""
herd/calculator.py — HERD Index 합산 계산기
6개 지표를 가중합산해 0~100 단일 점수를 산출하고 5단계를 판정한다.
티커 하나를 받으면 수집→계산→합산까지 전체 파이프라인을 자동 실행한다.
"""

import logging
from typing import TypedDict

from config.settings import HERD_THRESHOLDS, HERD_WEIGHTS
from collectors.finnhub_collector import get_eps_surprise_multiplier
from collectors.sector_collector import get_sector_multiplier
from collectors.stock_collector import collect
from indicators.rsi import calc_weekly_rsi, calc_monthly_rsi
from indicators.price_position import calc_52w_position, calc_ma200_deviation
from indicators.volume import calc_volume_strength
from indicators.ma200_weekly import calc_ma200_weekly

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# HERD 5단계 경계값
# ──────────────────────────────────────────────
SCATTER_UPPER = 40.0
DRIFT_LOWER = 60.0


# ──────────────────────────────────────────────
# 반환 타입 정의
# ──────────────────────────────────────────────
class IndicatorValues(TypedDict):
    weekly_rsi:      float
    monthly_rsi:     float
    position_52w:    float
    ma200_deviation: float
    volume_strength: float
    ma200_weekly:    float   # 200주 이동평균 위치 (v2 신규 추가)


class HerdScoreBreakdown(TypedDict):
    herd_base:         float
    eps_multiplier:    float
    sector_multiplier: float
    herd_v4:           float


class HerdResult(TypedDict):
    ticker:            str
    score:             float
    stage:             str
    indicators:        IndicatorValues
    herd_base:         float
    eps_multiplier:    float
    sector_multiplier: float
    herd_v4:           float


def get_stage(score: float) -> str:
    """
    HERD 점수를 입력받아 5단계 중 하나를 반환한다.
    경계값은 settings.py의 HERD_THRESHOLDS와 Action Layer 기준을 따른다.
    """
    if score <= HERD_THRESHOLDS["flee"]:
        return "Herd Flee"
    if score <= SCATTER_UPPER:
        return "Herd Scatter"
    if score < DRIFT_LOWER:
        return "Herd Calm"
    if score < HERD_THRESHOLDS["rush"]:
        return "Herd Drift"
    return "Herd Rush"


def calc_herd_score(indicators: IndicatorValues) -> float:
    """
    6개 지표값을 HERD_WEIGHTS로 가중합산해 HERD 점수를 반환한다.

    Args:
        indicators: 6개 지표 딕셔너리

    Returns:
        HERD 점수 (0~100 float)
    """
    # settings.py 키 → indicators 딕셔너리 키 매핑
    # (52w_position: settings 키명과 indicator 키명이 다름에 유의)
    key_map = {
        "monthly_rsi":     "monthly_rsi",
        "weekly_rsi":      "weekly_rsi",
        "52w_position":    "position_52w",
        "ma200_deviation": "ma200_deviation",
        "volume_strength": "volume_strength",
        "ma200_weekly":    "ma200_weekly",    # 200주 MA 위치
    }

    score = 0.0
    for settings_key, indicator_key in key_map.items():
        weight = HERD_WEIGHTS[settings_key]
        value  = indicators[indicator_key]
        score += weight * value

    return round(float(max(0.0, min(100.0, score))), 2)


def calc_herd_scores(
    indicators: IndicatorValues,
    eps_multiplier: float = 1.0,
    sector_multiplier: float = 1.0,
) -> HerdScoreBreakdown:
    """
    HERD v3 기본 점수와 v4 보정 점수를 함께 반환한다.

    calc_herd_score()의 float 반환 호환성을 유지하기 위해 v4 확장값은
    별도 함수에서 계산한다.
    """
    herd_base = calc_herd_score(indicators)
    adjusted = herd_base * eps_multiplier * sector_multiplier
    herd_v4 = round(float(max(0.0, min(100.0, adjusted))), 2)

    return HerdScoreBreakdown(
        herd_base         = herd_base,
        eps_multiplier    = round(float(eps_multiplier), 2),
        sector_multiplier = round(float(sector_multiplier), 2),
        herd_v4           = herd_v4,
    )


def _safe_eps_multiplier(ticker: str) -> float:
    """EPS 보정 승수 조회 실패 시 1.0으로 폴백한다."""
    try:
        return get_eps_surprise_multiplier(ticker)
    except Exception as e:
        logger.warning(f"[{ticker}] EPS 보정 실패 — 기본값 1.0 사용: {e}")
        return 1.0


def _safe_sector_multiplier(ticker: str) -> float:
    """섹터 상대 강도 보정 승수 조회 실패 시 1.0으로 폴백한다."""
    try:
        return get_sector_multiplier(ticker)
    except Exception as e:
        logger.warning(f"[{ticker}] 섹터 보정 실패 — 기본값 1.0 사용: {e}")
        return 1.0


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

    # 2. 6개 지표 계산 — 각각 개별 예외처리 후 한 번에 실패 판단
    indicator_funcs = {
        "weekly_rsi":      lambda: calc_weekly_rsi(df),
        "monthly_rsi":     lambda: calc_monthly_rsi(df),
        "position_52w":    lambda: calc_52w_position(df),
        "ma200_deviation": lambda: calc_ma200_deviation(df),
        "volume_strength": lambda: calc_volume_strength(df),
        "ma200_weekly":    lambda: calc_ma200_weekly(df),   # 200주 MA 위치
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
        ma200_weekly    = values["ma200_weekly"],
    )

    # 3. 가중합산 + HERD v4 보정 및 단계 판정
    breakdown = calc_herd_scores(
        indicators,
        eps_multiplier    = _safe_eps_multiplier(ticker),
        sector_multiplier = _safe_sector_multiplier(ticker),
    )
    score = breakdown["herd_v4"]
    stage = get_stage(score)

    result = HerdResult(
        ticker            = ticker.upper(),
        score             = score,
        stage             = stage,
        indicators        = indicators,
        herd_base         = breakdown["herd_base"],
        eps_multiplier    = breakdown["eps_multiplier"],
        sector_multiplier = breakdown["sector_multiplier"],
        herd_v4           = breakdown["herd_v4"],
    )

    logger.info(
        f"[{ticker}] HERD v4 = {score:.2f} ({stage}) "
        f"base={breakdown['herd_base']:.2f} "
        f"eps×{breakdown['eps_multiplier']:.2f} "
        f"sector×{breakdown['sector_multiplier']:.2f}"
    )
    return result
