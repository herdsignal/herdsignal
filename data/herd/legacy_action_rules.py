"""DB와 무관하게 재현 가능한 기존 Python v6.1 가격 행동 규칙."""

from __future__ import annotations

import pandas as pd

RUSH_THRESHOLD = 75.0
DRIFT_LOWER = 60.0
FLEE_THRESHOLD = 15.0
SCATTER_UPPER = 40.0


def trend_frame(close: pd.Series) -> pd.DataFrame:
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()
    high_52w = close.rolling(252).max()
    low_52w = close.rolling(252).min()
    ma200_slope = ma200.pct_change(63) * 100
    ma200_deviation = (close / ma200 - 1) * 100
    position_52w = (close - low_52w) / (high_52w - low_52w) * 100
    quality = pd.Series(0.0, index=close.index)
    quality += (close > ma200).astype(float) * 25
    quality += (ma50 > ma200).astype(float) * 20
    quality += (ma200_slope > 0).astype(float) * 20
    quality += (ma200_deviation > -20).astype(float) * 15
    quality += (position_52w > 35).astype(float) * 20
    return pd.DataFrame({
        "ma200_deviation": ma200_deviation,
        "position_52w": position_52w,
        "trend_quality": quality.clip(0, 100),
        "return_63d": close.pct_change(63) * 100,
        "return_21d": close.pct_change(21) * 100,
        "drawdown_52w": (close / high_52w - 1) * 100,
    })


def action_decision(score: float, context: pd.Series, profile: str = "v61") -> tuple[str, str, float]:
    trend = float(context.get("trend_quality", 50) or 50)
    deviation = float(context.get("ma200_deviation", 0) or 0)
    balanced = profile in {"balanced", "v61"}

    if score >= RUSH_THRESHOLD:
        if balanced and trend >= 75 and deviation < 45:
            return "HEALTHY_RUSH", "SELL", 0.05
        if balanced and trend >= 70 and deviation < 65:
            return "HEALTHY_RUSH", "SELL", 0.08
        if trend >= 70 and deviation < 65:
            return "HEALTHY_RUSH", "HOLD", 0.0
        if trend < 45 or deviation > 90:
            return "CROWDED_RUSH", "SELL", 0.30 if balanced else 0.20
        return "NORMAL_RUSH", "SELL", 0.15 if balanced else 0.08

    if score >= DRIFT_LOWER:
        if trend >= 75:
            return "HEALTHY_DRIFT", "SELL", 0.02 if balanced else 0.0
        if not balanced and trend >= 65:
            return "HEALTHY_DRIFT", "HOLD", 0.0
        return "NORMAL_DRIFT", "SELL", 0.06 if balanced else 0.03

    if score <= FLEE_THRESHOLD:
        if trend >= 55 and deviation > -25:
            return "OPPORTUNITY_FLEE", "BUY", 0.22 if balanced else 0.30
        if trend < 35 or deviation < -35:
            return ("BROKEN_FLEE", "HOLD", 0.0) if balanced else ("BROKEN_FLEE", "BUY", 0.05)
        return "NORMAL_FLEE", "BUY", 0.08 if balanced else 0.15

    if score <= SCATTER_UPPER:
        if trend >= 60 and deviation > -20:
            return "OPPORTUNITY_SCATTER", "BUY", 0.04 if balanced else 0.10
        return "NORMAL_SCATTER", "HOLD", 0.0

    return "CALM", "HOLD", 0.0
