"""기존 신호를 바꾸지 않고 행동 비율 상한만 적용하는 Risk Cap 후보."""

from __future__ import annotations

from statistics import median

import pandas as pd

PROFILES = {
    "off": {"weak_buy": 1.0, "moderate_buy": 1.0, "strong_sell": 1.0, "global": 1.0},
    "balanced": {"weak_buy": 0.05, "moderate_buy": 0.08, "strong_sell": 0.08, "global": 0.20},
    "strict": {"weak_buy": 0.02, "moderate_buy": 0.05, "strong_sell": 0.05, "global": 0.12},
}


def capped_decision(base_decide, profile_name: str):
    profile = PROFILES[profile_name]

    def decide(score, trend, previous, action_days):
        action, ratio = base_decide(score, trend, previous, action_days)
        if ratio <= 0 or profile_name == "off": return action, ratio
        quality = float(trend.get("trend_quality", 50) or 50)
        ret = trend.get("return_63d")
        ret = float(ret) if pd.notna(ret) else 0.0
        cap = profile["global"]
        if action == "BUY":
            if quality < 45 or ret < -10: cap = min(cap, profile["weak_buy"])
            elif quality < 55: cap = min(cap, profile["moderate_buy"])
        elif action == "SELL" and quality >= 70 and ret > 5:
            cap = min(cap, profile["strong_sell"])
        return action, round(min(ratio, cap), 2)
    return decide


def summarize_risk_cap(rows: list[dict]) -> dict:
    returns = [r["candidate_return"] - r["baseline_return"] for r in rows]
    mdds = [r["candidate_mdd"] - r["baseline_mdd"] for r in rows]
    return {
        "samples": len(rows),
        "return_improvement_rate": sum(v > 0.05 for v in returns) / len(rows) * 100,
        "return_underperformance_rate": sum(v < -0.05 for v in returns) / len(rows) * 100,
        "median_return_delta": median(returns),
        "mdd_improvement_rate": sum(v > 0.05 for v in mdds) / len(rows) * 100,
        "mdd_underperformance_rate": sum(v < -0.05 for v in mdds) / len(rows) * 100,
        "median_mdd_delta": median(mdds),
        "joint_improvement_rate": sum(r > 0.05 and m > 0.05 for r, m in zip(returns, mdds)) / len(rows) * 100,
        "trade_reduction_median": median(r["baseline_actions"] - r["candidate_actions"] for r in rows),
    }

