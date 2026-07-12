"""횡보장 행동 억제 후보의 판단과 결과 집계."""

from __future__ import annotations

from statistics import median

import pandas as pd


def is_sideways(trend: pd.Series, max_abs_return: float = 5.0) -> bool:
    quality = float(trend.get("trend_quality", 50) or 50)
    return_63d = trend.get("return_63d")
    return pd.notna(return_63d) and abs(float(return_63d)) <= max_abs_return and 35 <= quality <= 65


def suppress_decision(base_decide, factor: float):
    def decide(score, trend, previous, action_days):
        action, ratio = base_decide(score, trend, previous, action_days)
        if ratio > 0 and is_sideways(trend):
            ratio = round(ratio * factor, 2)
            if ratio <= 0: return "HOLD", 0.0
        return action, ratio
    return decide


def summarize_experiment(rows: list[dict]) -> dict:
    deltas = [row["candidate_return"] - row["baseline_return"] for row in rows]
    mdd_deltas = [row["candidate_mdd"] - row["baseline_mdd"] for row in rows]
    return {
        "samples": len(rows),
        "return_improvement_rate": sum(delta > 0.05 for delta in deltas) / len(rows) * 100,
        "return_underperformance_rate": sum(delta < -0.05 for delta in deltas) / len(rows) * 100,
        "median_return_delta": median(deltas),
        "mdd_improvement_rate": sum(delta > 0.05 for delta in mdd_deltas) / len(rows) * 100,
        "mdd_underperformance_rate": sum(delta < -0.05 for delta in mdd_deltas) / len(rows) * 100,
        "median_mdd_delta": median(mdd_deltas),
        "trade_reduction_median": median(row["baseline_actions"] - row["candidate_actions"] for row in rows),
    }

