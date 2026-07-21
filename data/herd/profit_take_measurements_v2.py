"""부분 익절 V2 사전등록 검증과 네 독립 가격 측정값을 계산한다."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


REGISTRY_PATH = Path(__file__).with_name("profit_take_measurements_v2.json")
REGISTRY_VERSION = "HERD_PROFIT_TAKE_MEASUREMENTS_V2"
MEASUREMENT_COLUMNS = {
    "PROFIT_RELATIVE_EXTENSION_V2": "relative_extension",
    "PROFIT_TREND_DECELERATION_V2": "trend_deceleration",
    "PROFIT_RELATIVE_BREAK_V2": "relative_break",
    "PROFIT_DOWNSIDE_EXPANSION_V2": "downside_expansion",
}


class ProfitTakeMeasurementV2Error(ValueError):
    """사전등록이 완화되거나 입력 시계열이 잘못됐을 때 발생한다."""


def validate_registry(registry: dict[str, Any]) -> dict[str, Any]:
    if registry.get("registry_version") != REGISTRY_VERSION \
            or registry.get("status") != "LOCKED_BEFORE_OOS_RESULTS":
        raise ProfitTakeMeasurementV2Error("measurement registry is not locked")
    hypotheses = registry.get("hypotheses", [])
    ids = {item["id"] for item in hypotheses}
    if ids != set(MEASUREMENT_COLUMNS) or len(hypotheses) != 4:
        raise ProfitTakeMeasurementV2Error("exactly four independent hypotheses are required")
    if any(item.get("event_percentiles") != [0.8, 0.9] for item in hypotheses):
        raise ProfitTakeMeasurementV2Error("event percentiles changed")
    gate = registry.get("oos_gate", {})
    if gate.get("minimum_test_folds", 0) < 4 or gate.get("minimum_directional_folds", 0) < 3:
        raise ProfitTakeMeasurementV2Error("OOS gate is too weak")
    forbidden = set(registry.get("forbidden", []))
    if "HIGH_HERD_ALONE_AS_EVENT" not in forbidden \
            or "AUTHORIZE_ACTION_BEFORE_ADMISSION" not in forbidden:
        raise ProfitTakeMeasurementV2Error("unsafe shortcut is not forbidden")
    return {"registry_version": REGISTRY_VERSION, "hypothesis_count": 4, "locked": True}


def load_registry(path: Path = REGISTRY_PATH) -> tuple[dict, dict]:
    registry = json.loads(path.read_text(encoding="utf-8"))
    return registry, validate_registry(registry)


def _log_slope(series: pd.Series, window: int) -> pd.Series:
    x = np.arange(window, dtype=float)
    centered = x - x.mean()
    denominator = float(np.square(centered).sum())
    return np.log(series).rolling(window).apply(
        lambda values: float(np.dot(centered, values - values.mean()) / denominator),
        raw=True,
    )


def _downside_volatility(returns: pd.Series, window: int) -> pd.Series:
    downside = returns.clip(upper=0.0)
    return downside.rolling(window).std(ddof=1) * np.sqrt(252.0)


def expanding_percentile(series: pd.Series, minimum_history: int = 756) -> pd.Series:
    """현재 값을 제외한 과거 일별 분포에서 percentile을 계산한다."""
    values = series.to_numpy(dtype=float)
    output = np.full(len(series), np.nan)
    for index, value in enumerate(values):
        history = values[:index]
        history = history[np.isfinite(history)]
        if np.isfinite(value) and len(history) >= minimum_history:
            output[index] = float((history <= value).mean())
    return pd.Series(output, index=series.index, dtype=float)


def calculate_measurements(
    stock_close: pd.Series,
    sector_close: pd.Series,
    spy_close: pd.Series,
    *,
    minimum_history: int = 756,
) -> pd.DataFrame:
    aligned = pd.concat(
        [stock_close.rename("stock"), sector_close.rename("sector"), spy_close.rename("spy")],
        axis=1,
        join="inner",
    ).dropna()
    if aligned.empty or (aligned <= 0).any().any():
        raise ProfitTakeMeasurementV2Error("positive aligned prices are required")

    stock = aligned["stock"]
    sector = aligned["sector"]
    returns = stock.pct_change(fill_method=None)
    relative_21 = stock.pct_change(21, fill_method=None) - sector.pct_change(21, fill_method=None)
    relative_126 = stock.pct_change(126, fill_method=None) - sector.pct_change(126, fill_method=None)
    slope_21 = _log_slope(stock, 21)
    slope_63 = _log_slope(stock, 63)
    slope_126 = _log_slope(stock, 126)

    frame = pd.DataFrame(index=aligned.index)
    frame["relative_extension"] = stock.pct_change(252, fill_method=None) - sector.pct_change(252, fill_method=None)
    frame["trend_deceleration"] = -(slope_21 - slope_63)
    frame.loc[slope_126 <= 0, "trend_deceleration"] = np.nan
    frame["relative_break"] = -(relative_21 - relative_126 / 6.0)
    frame["downside_expansion"] = _downside_volatility(returns, 20) / _downside_volatility(returns, 63).replace(0, np.nan)
    frame["stock_close"] = stock
    frame["sector_close"] = sector
    frame["spy_close"] = aligned["spy"]
    for hypothesis, column in MEASUREMENT_COLUMNS.items():
        frame[f"{hypothesis}_percentile"] = expanding_percentile(
            frame[column], minimum_history=minimum_history
        )
    return frame
