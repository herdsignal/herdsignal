"""에너지·소재 취약 구간용 제한된 Action Ratio 보정 후보."""

from __future__ import annotations

import pandas as pd

TARGET_GROUPS = {"energy", "materials"}


def build_sector_ratio_factor(stock: pd.Series, sector: pd.Series, market: pd.Series, group: str) -> pd.Series:
    index = stock.index
    if group not in TARGET_GROUPS:
        return pd.Series(1.0, index=index)
    aligned = pd.concat([stock.rename("stock"), sector.rename("sector"), market.rename("market")], axis=1).reindex(index).ffill()
    stock_sector = aligned["stock"].pct_change(63) - aligned["sector"].pct_change(63)
    sector_market = aligned["sector"].pct_change(63) - aligned["market"].pct_change(63)
    sector_trend = aligned["sector"] / aligned["sector"].rolling(200).mean() - 1
    volatility = aligned["stock"].pct_change().rolling(63).std() * (252 ** 0.5)
    factor = pd.Series(1.0, index=index)
    factor += ((stock_sector < -0.10) & (sector_market < -0.05)).astype(float) * 0.05
    factor += (sector_trend < -0.10).astype(float) * 0.05
    factor += (volatility > 0.45).astype(float) * 0.05
    factor -= ((stock_sector > 0.10) & (sector_market > 0.05) & (sector_trend > 0)).astype(float) * 0.05
    return factor.clip(0.9, 1.1).fillna(1.0)


def apply_sector_ratio(action: str, ratio: float, context: pd.Series) -> tuple[str, float]:
    factor = float(context.get("sector_ratio_factor", 1.0))
    return action, round(min(0.5, max(0.0, ratio * factor)), 3)
