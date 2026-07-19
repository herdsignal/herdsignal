"""차세대 HERD B0~B4 후보를 구성하고 동일 조건에서 ablation 평가한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from collectors.stock_collector import collect
from herd.benchmark_engine import BenchmarkConfig, buy_and_hold, performance_metrics, simulate
from herd.evidence_family_validation import build_evidence_scores
from herd.indicator_inventory import build_v4_indicator_frame
from herd.legacy_model_evaluation import v4_base_score
from herd.validation_universe import TICKERS, UNIVERSE_VERSION

CANDIDATES = ("B0", "B1", "B2", "B3")


def _monthly_targets_on_daily(monthly: pd.Series, daily_index: pd.Index) -> pd.Series:
    targets = pd.Series(np.nan, index=daily_index, dtype=float)
    for month_end, target in monthly.dropna().items():
        observed = daily_index[daily_index <= month_end]
        if len(observed):
            targets.loc[observed[-1]] = float(target)
    return targets


def classify_rush(
    trend_score: pd.Series,
    participation_score: pd.Series,
    risk_score: pd.Series,
) -> pd.Series:
    result = pd.Series("NOT_RUSH", index=trend_score.index, dtype=object)
    rush = trend_score >= 75
    healthy = rush & (participation_score >= 50) & (risk_score >= 40)
    result.loc[rush] = "EXHAUSTED_RUSH"
    result.loc[healthy] = "HEALTHY_RUSH"
    return result


def build_candidate_targets(
    scores: dict[str, pd.Series],
    daily_index: pd.Index,
    *,
    v4_score: pd.Series,
) -> dict[str, pd.Series]:
    trend = scores["trend_relative_strength"]
    participation = scores["participation"].reindex(trend.index)
    risk = scores["risk"].reindex(trend.index)

    # B0: 현재 가격 기반 v4 행동을 목표 비중 형태로 고정한 비교 기준.
    b0_monthly = pd.Series(
        np.select(
            [v4_score >= 75, v4_score >= 60, v4_score <= 15, v4_score <= 40],
            [0.70, 0.95, 1.0, 1.0],
            default=1.0,
        ),
        index=v4_score.index,
    )
    # B1: 장기 복리를 우선하고 추세 훼손 때만 제한적으로 현금을 둔다.
    b1_monthly = pd.Series(
        np.select([trend >= 40, trend >= 25], [1.0, 0.75], default=0.50),
        index=trend.index,
    )
    # B2: 참여는 방향 점수가 아니라 약한 추세의 감축 확인 조건으로만 쓴다.
    b2_monthly = b1_monthly.copy()
    weak_confirmation = (trend < 40) & (participation < 40)
    b2_monthly.loc[weak_confirmation] = (b2_monthly.loc[weak_confirmation] - 0.25).clip(0.5, 1.0)
    # Healthy Rush는 유지하고 Exhausted Rush에서만 일부 노출을 낮춘다.
    rush = classify_rush(
        trend,
        participation,
        pd.Series(100.0, index=trend.index),
    )
    b2_monthly.loc[rush == "HEALTHY_RUSH"] = 1.0
    b2_monthly.loc[rush == "EXHAUSTED_RUSH"] = 0.85
    # B3: 위험은 방향 점수에 합산하지 않고 최대 노출만 제한한다.
    risk_cap = pd.Series(
        np.select([risk >= 40, risk >= 25], [1.0, 0.90], default=0.75),
        index=risk.index,
    )
    b3_monthly = pd.concat([b2_monthly, risk_cap], axis=1).min(axis=1)

    return {
        "B0": _monthly_targets_on_daily(b0_monthly, daily_index),
        "B1": _monthly_targets_on_daily(b1_monthly, daily_index),
        "B2": _monthly_targets_on_daily(b2_monthly, daily_index),
        "B3": _monthly_targets_on_daily(b3_monthly, daily_index),
    }


def _summary(rows: list[dict], candidate: str) -> dict:
    values = [row["candidates"][candidate] for row in rows]

    def median(key: str) -> float | None:
        valid = [float(value[key]) for value in values if value.get(key) is not None]
        return float(np.median(valid)) if valid else None

    excess = [value["excess_cagr"] for value in values if value.get("excess_cagr") is not None]
    mdd_improvement = [
        row["candidates"][candidate]["max_drawdown"] - row["buy_hold"]["max_drawdown"]
        for row in rows
    ]
    return {
        "tickers": len(values),
        "median_cagr": median("cagr"),
        "median_excess_cagr": median("excess_cagr"),
        "positive_excess_rate": sum(value > 0 for value in excess) / len(excess) * 100,
        "median_mdd_improvement": float(np.median(mdd_improvement)),
        "median_upside_capture": median("upside_capture"),
        "median_downside_capture": median("downside_capture"),
        "median_turnover": median("turnover"),
    }


def evaluate(price_frames: dict[str, pd.DataFrame]) -> dict:
    closes = pd.concat(
        {ticker: frame.set_index("Date")["Close"] for ticker, frame in price_frames.items()}, axis=1
    )
    volumes = pd.concat(
        {ticker: frame.set_index("Date")["Volume"] for ticker, frame in price_frames.items()}, axis=1
    )
    evidence = build_evidence_scores(closes, volumes)
    config = BenchmarkConfig()
    rows = []
    for ticker, raw in price_frames.items():
        prices = raw.set_index("Date")[["Open", "Close"]].sort_index()
        indicator_frame = build_v4_indicator_frame(raw)
        v4 = v4_base_score(indicator_frame).resample("ME").last()
        ticker_scores = {name: frame[ticker].dropna() for name, frame in evidence.items()}
        start = max([v4.first_valid_index(), *(score.first_valid_index() for score in ticker_scores.values())])
        prices = prices.loc[start:]
        benchmark = buy_and_hold(prices, config=config)
        targets = build_candidate_targets(ticker_scores, prices.index, v4_score=v4)
        candidates = {
            name: performance_metrics(simulate(name, prices, target, config=config), benchmark)
            for name, target in targets.items()
        }
        rows.append(
            {
                "ticker": ticker,
                "buy_hold": performance_metrics(benchmark),
                "candidates": candidates,
            }
        )
    return {
        "report_version": "2026.07-v1",
        "universe_version": UNIVERSE_VERSION,
        "candidate_contract": {
            "B0": "price-only v4 baseline expressed as target exposure",
            "B1": "deduplicated trend/relative-strength core",
            "B2": "B1 + participation confirmation + Healthy/Exhausted Rush",
            "B3": "B2 + independent risk exposure cap",
            "B4": "BLOCKED_DATA_NOT_READY: point-in-time business evidence unavailable",
        },
        "summary": {name: _summary(rows, name) for name in CANDIDATES},
        "rows": rows,
    }


def run(period: str = "10y") -> dict:
    frames, failures = {}, {}
    for ticker in TICKERS:
        try:
            frame = collect(ticker, period=period)
            frame["Date"] = pd.to_datetime(frame["Date"])
            frames[ticker] = frame
        except Exception as exc:
            failures[ticker] = str(exc)
    report = evaluate(frames)
    report["failures"] = failures
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--period", default="10y")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(run(args.period), ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
