"""과거 HERD 지표 계산에 필요한 최소 가격 이력을 검사한다."""

from __future__ import annotations

import pandas as pd

from indicators.ma200_weekly import MIN_WEEKLY_CANDLES
from indicators.price_position import MA_PERIOD, TRADING_DAYS_1Y
from indicators.rsi import MIN_CANDLES
from indicators.volume import MIN_ROWS


def is_history_ready(df: pd.DataFrame) -> bool:
    """모든 HERD 기본 지표를 계산할 수 있는 최소 이력이 있는지 반환한다."""
    if df.empty or "Date" not in df.columns:
        return False

    required_daily = max(TRADING_DAYS_1Y, MA_PERIOD, MIN_ROWS)
    if len(df) < required_daily:
        return False

    dated = df.copy()
    dated["Date"] = pd.to_datetime(dated["Date"])
    close = dated.set_index("Date")["Close"]
    weekly_count = len(close.resample("W").last().dropna())
    monthly_count = len(close.resample("ME").last().dropna())

    return (
        weekly_count >= max(MIN_CANDLES, MIN_WEEKLY_CANDLES)
        and monthly_count >= MIN_CANDLES
    )
