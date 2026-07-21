"""HERD에서 사용하는 Wilder 방식 RSI의 최소 구현."""

from __future__ import annotations

import pandas as pd


def wilder_rsi(close: pd.Series, period: int = 14) -> pd.Series | None:
    """기존 pandas_ta RSI 계약과 동일한 시계열을 반환한다.

    HERD 운영 계약은 ``adjust=False``인 Wilder RMA와 첫 변화량부터 시작하는
    초기화 방식을 사용한다. 입력이 ``period + 1``개보다 짧으면 기존처럼
    계산 불가를 ``None``으로 표현한다.
    """
    if period <= 0:
        raise ValueError("period must be positive")
    if close is None or len(close) < period + 1:
        return None

    values = close.astype(float)
    change = values.diff()
    gain = change.clip(lower=0.0)
    loss = change.clip(upper=0.0)
    average_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    average_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()
    result = 100.0 * average_gain / (average_gain + average_loss.abs())
    result.name = f"RSI_{period}"
    return result
