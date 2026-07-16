"""HERD 행동 단위 사후 정확도 분석.

포트폴리오 총수익과 별개로 각 BUY/SELL 결정 이후의 가격 경로와
동일 비중으로 아무 행동도 하지 않은 반사실(counterfactual)을 비교한다.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any

import pandas as pd

from herd.validation_v2 import DecisionFn, normalize_price_frame

FORWARD_WINDOWS = {"1m": 21, "3m": 63, "6m": 126}


def _herd_stage(score: float) -> str:
    if score <= 15: return "flee"
    if score <= 40: return "scatter"
    if score < 60: return "calm"
    if score < 75: return "drift"
    return "rush"


def _lifecycle(days: int) -> str:
    if days <= 5: return "early"
    if days <= 20: return "progressing"
    if days <= 45: return "mature"
    return "persistent"


def _ratio_bucket(ratio: float) -> str:
    if ratio <= 0.05: return "0-5%"
    if ratio <= 0.15: return "5-15%"
    if ratio <= 0.30: return "15-30%"
    return "30%+"


def _market_regime(context: pd.Series) -> str:
    ret = context.get("return_63d")
    if pd.isna(ret): return "unknown"
    if float(ret) <= -5: return "bear"
    if float(ret) >= 5: return "bull"
    return "sideways"


def _event_metrics(close: pd.Series, position: int, side: str, ratio: float) -> dict[str, float | None]:
    start = float(close.iloc[position])
    metrics: dict[str, float | None] = {}
    for label, days in FORWARD_WINDOWS.items():
        end_position = position + days
        if end_position >= len(close):
            metrics[f"return_{label}"] = None
            metrics[f"drawdown_{label}"] = None
            metrics[f"counterfactual_delta_{label}"] = None
            metrics[f"hit_{label}"] = None
            continue
        window = close.iloc[position : end_position + 1]
        forward_return = (float(window.iloc[-1]) / start - 1) * 100
        drawdown = (float(window.min()) / start - 1) * 100
        metrics[f"return_{label}"] = forward_return
        metrics[f"drawdown_{label}"] = drawdown
        metrics[f"counterfactual_delta_{label}"] = ratio * forward_return * (1 if side == "BUY" else -1)
        metrics[f"hit_{label}"] = forward_return > 0 if side == "BUY" else forward_return < 0
    return metrics


def collect_action_events(
    prices: pd.DataFrame,
    herd: pd.Series,
    trend: pd.DataFrame,
    decide: DecisionFn,
    cooldown_days: int = 20,
) -> list[dict[str, Any]]:
    """실행 가능한 행동일을 추출하고 이후 성과를 붙인다."""
    frame = normalize_price_frame(prices)
    close = frame["Close"]
    herd = herd.reindex(frame.index).ffill()
    trend = trend.reindex(frame.index).ffill()
    previous_score: float | None = None
    previous_action = "HOLD"
    action_days = 0
    last_action = {"BUY": -cooldown_days - 1, "SELL": -cooldown_days - 1}
    events: list[dict[str, Any]] = []

    for i, date in enumerate(frame.index):
        score = herd.get(date)
        if pd.isna(score):
            continue
        score = float(score)
        action, ratio = decide(score, trend.loc[date], previous_score, action_days)
        action_days = action_days + 1 if action == previous_action else 1
        previous_action = action
        previous_score = score
        if action not in last_action or ratio <= 0 or i - last_action[action] <= cooldown_days:
            continue
        last_action[action] = i
        metrics = _event_metrics(close, i, action, ratio)
        events.append({
            "date": str(date.date()), "side": action, "ratio": ratio, "score": score,
            "herd_stage": _herd_stage(score), "lifecycle": _lifecycle(action_days),
            "ratio_bucket": _ratio_bucket(ratio), "market_regime": _market_regime(trend.loc[date]),
            **metrics,
        })
    return events


def _group_summary(events: list[dict[str, Any]], key: str) -> dict[str, dict[str, float | int | None]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        groups[str(event[key])].append(event)
    result = {}
    for name, rows in sorted(groups.items()):
        result[name] = {
            "samples": len(rows),
            "horizons": {
                label: _horizon_summary(rows, label)
                for label in FORWARD_WINDOWS
            },
        }
    return result


def _horizon_summary(events: list[dict[str, Any]], label: str) -> dict[str, float | int | None]:
    completed = [event for event in events if event[f"hit_{label}"] is not None]
    hits = [event[f"hit_{label}"] for event in completed]
    returns = [event[f"return_{label}"] for event in completed]
    drawdowns = [event[f"drawdown_{label}"] for event in completed]
    deltas = [event[f"counterfactual_delta_{label}"] for event in completed]
    return {
        "samples": len(completed),
        "hit_rate": sum(hits) / len(hits) * 100 if hits else None,
        "forward_return_mean": mean(returns) if returns else None,
        "drawdown_mean": mean(drawdowns) if drawdowns else None,
        "counterfactual_delta_mean": mean(deltas) if deltas else None,
    }


def summarize_action_accuracy(events: list[dict[str, Any]]) -> dict[str, Any]:
    """행동 방향과 주요 분류축별 정확도 요약을 반환한다."""
    completed = [event for event in events if event["hit_3m"] is not None]
    hits = [event["hit_3m"] for event in completed]
    return {
        "event_count": len(events),
        "completed_3m_count": len(completed),
        "hit_rate_3m": sum(hits) / len(hits) * 100 if hits else None,
        "horizons": {
            label: _horizon_summary(events, label)
            for label in FORWARD_WINDOWS
        },
        "by_side": _group_summary(events, "side"),
        "by_ratio": _group_summary(events, "ratio_bucket"),
        "by_lifecycle": _group_summary(events, "lifecycle"),
        "by_herd_stage": _group_summary(events, "herd_stage"),
        "by_market_regime": _group_summary(events, "market_regime"),
    }


def summarize_many_action_accuracy(results: list[dict[str, Any]]) -> dict[str, Any]:
    """종목별 행동 이벤트를 합쳐 전체 1·3·6개월 결과를 계산한다."""
    events = [
        _with_legacy_hits(event)
        for result in results
        for event in result.get("events", [])
    ]
    return {
        "event_count": len(events),
        "horizons": {
            label: _horizon_summary(events, label)
            for label in FORWARD_WINDOWS
        },
        "by_side": _group_summary(events, "side"),
    }


def _with_legacy_hits(event: dict[str, Any]) -> dict[str, Any]:
    """이전 리포트의 이벤트에도 새 기간별 적중 필드를 복원한다."""
    normalized = dict(event)
    for label in FORWARD_WINDOWS:
        key = f"hit_{label}"
        if key in normalized:
            continue
        forward_return = normalized.get(f"return_{label}")
        normalized[key] = (
            None if forward_return is None
            else forward_return > 0 if normalized.get("side") == "BUY"
            else forward_return < 0
        )
    return normalized


def evaluate_action_accuracy(
    prices: pd.DataFrame,
    herd: pd.Series,
    trend: pd.DataFrame,
    decide: DecisionFn,
    cooldown_days: int = 20,
) -> dict[str, Any]:
    events = collect_action_events(prices, herd, trend, decide, cooldown_days)
    return {"summary": summarize_action_accuracy(events), "events": events}
