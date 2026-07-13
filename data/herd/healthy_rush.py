"""장기 상승 종목의 조기 익절을 줄이기 위한 Rush 연구 후보."""

from __future__ import annotations

import pandas as pd


def classify_rush(context: pd.Series) -> tuple[str, str, float]:
    trend = float(context.get("trend_quality", 50))
    deviation = float(context.get("ma200_deviation", 0))
    return_21d = float(context.get("return_21d", 0))
    return_63d = float(context.get("return_63d", 0))
    drawdown = float(context.get("drawdown_52w", 0))

    if trend < 45 or drawdown <= -15 or return_63d < -10:
        return "BREAKING_RUSH", "SELL", 0.20
    if deviation >= 70 and (return_21d <= 0 or drawdown <= -8):
        return "EXHAUSTED_RUSH", "SELL", 0.10
    if trend >= 75 and return_21d > 0 and return_63d > 5:
        return "EXTENDING_RUSH", "HOLD", 0.0
    return "HEALTHY_RUSH", "HOLD", 0.0


def healthy_rush_decision(score: float, context: pd.Series, fallback) -> tuple[str, float]:
    if score < 75:
        return fallback()
    _regime, action, ratio = classify_rush(context)
    return action, ratio
