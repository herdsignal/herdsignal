"""HERD 후보에 넣기 전 증거군의 독립 효과를 검증한다."""

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
from herd.data_snapshot import load_snapshot
from herd.validation_universe import SECTOR_UNIVERSE, TICKERS, UNIVERSE_VERSION

FAMILIES = ("participation", "trend_relative_strength", "risk")


def _percentile_rank(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.rank(axis=1, pct=True, method="average") * 100


def build_evidence_scores(closes: pd.DataFrame, volumes: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """관측 시점까지의 가격·거래량만으로 월말 증거 점수를 만든다."""
    closes = closes.sort_index().ffill(limit=3)
    volumes = volumes.reindex_like(closes).fillna(0.0)
    monthly_close = closes.resample("ME").last()

    above_ma = (closes > closes.rolling(200, min_periods=200).mean()).astype(float)
    positive_63 = (closes.pct_change(63, fill_method=None) > 0).astype(float)
    market_breadth = (above_ma.mean(axis=1) + positive_63.mean(axis=1)) * 50
    volume_ratio = volumes.rolling(20, min_periods=20).mean() / volumes.rolling(
        120, min_periods=120
    ).mean().replace(0, np.nan)
    direction = np.sign(closes.pct_change(fill_method=None)).replace(0, np.nan)
    confirmed_volume = _percentile_rank((volume_ratio * direction).resample("ME").mean())
    monthly_breadth = market_breadth.resample("ME").last()
    breadth_frame = pd.DataFrame(
        np.repeat(monthly_breadth.to_numpy()[:, None], len(closes.columns), axis=1),
        index=monthly_breadth.index,
        columns=closes.columns,
    )
    participation = (
        confirmed_volume.mul(0.4)
        .add(breadth_frame.mul(0.6))
        .clip(0, 100)
    )

    momentum_12_1 = monthly_close.shift(1) / monthly_close.shift(12) - 1
    relative_strength = _percentile_rank(momentum_12_1)
    own_trend = (
        closes / closes.rolling(200, min_periods=200).mean().replace(0, np.nan) - 1
    ).resample("ME").last()
    own_trend_score = (50 + own_trend * 250).clip(0, 100)
    trend_rs = relative_strength.mul(0.5).add(own_trend_score.mul(0.5))

    returns = closes.pct_change(fill_method=None)
    downside_vol = returns.where(returns < 0, 0).rolling(63, min_periods=40).std()
    drawdown = closes / closes.rolling(252, min_periods=126).max() - 1
    low_downside_risk = 100 - _percentile_rank(downside_vol.resample("ME").last())
    drawdown_resilience = (100 + drawdown.resample("ME").last() * 250).clip(0, 100)
    risk = low_downside_risk.mul(0.5).add(drawdown_resilience.mul(0.5))

    return {
        "participation": participation,
        "trend_relative_strength": trend_rs,
        "risk": risk,
    }


def score_to_targets(score: pd.Series, daily_index: pd.Index) -> pd.Series:
    """독립 효과 측정용 고정 노출 규칙. 결과를 보고 임계값을 바꾸지 않는다."""
    monthly = pd.Series(
        np.select([score >= 60, score >= 40], [1.0, 0.5], default=0.0),
        index=score.index,
        dtype=float,
    )
    targets = pd.Series(np.nan, index=daily_index, dtype=float)
    for month_end, target in monthly.items():
        observed = daily_index[daily_index <= month_end]
        if len(observed):
            targets.loc[observed[-1]] = target
    # 마지막 거래일 종가까지의 월말 관측을 다음 거래일 시가에 한 번만 실행한다.
    return targets


def _summary(rows: list[dict], family: str) -> dict:
    values = [row["families"][family] for row in rows if family in row["families"]]

    def median(key: str) -> float | None:
        valid = [float(value[key]) for value in values if value.get(key) is not None]
        return float(np.median(valid)) if valid else None

    excess = [value["excess_cagr"] for value in values if value.get("excess_cagr") is not None]
    return {
        "tickers": len(values),
        "median_excess_cagr": median("excess_cagr"),
        "positive_excess_rate": sum(value > 0 for value in excess) / len(excess) * 100 if excess else None,
        "median_max_drawdown": median("max_drawdown"),
        "median_upside_capture": median("upside_capture"),
        "median_downside_capture": median("downside_capture"),
        "median_turnover": median("turnover"),
        "median_forward_12m_rank_ic": median("forward_12m_rank_ic"),
        "median_high_minus_low_12m_return": median("high_minus_low_12m_return"),
    }


def _predictive_metrics(score: pd.Series, close: pd.Series) -> dict[str, float | None]:
    monthly_close = close.resample("ME").last()
    forward_return = monthly_close.shift(-12) / monthly_close - 1
    aligned = pd.concat(
        [score.rename("score"), forward_return.rename("forward")],
        axis=1,
    ).dropna()
    if len(aligned) < 24:
        return {
            "forward_12m_rank_ic": None,
            "high_minus_low_12m_return": None,
        }
    high = aligned.loc[aligned["score"] >= 60, "forward"]
    low = aligned.loc[aligned["score"] < 40, "forward"]
    spread = float(high.mean() - low.mean()) if len(high) and len(low) else None
    return {
        "forward_12m_rank_ic": float(aligned["score"].corr(aligned["forward"], method="spearman")),
        "high_minus_low_12m_return": spread,
    }


def evaluate(
    price_frames: dict[str, pd.DataFrame],
    *,
    config: BenchmarkConfig | None = None,
    data_source: dict | None = None,
) -> dict:
    closes = pd.concat(
        {ticker: frame.set_index("Date")["Close"] for ticker, frame in price_frames.items()},
        axis=1,
    )
    volumes = pd.concat(
        {ticker: frame.set_index("Date")["Volume"] for ticker, frame in price_frames.items()},
        axis=1,
    )
    scores = build_evidence_scores(closes, volumes)
    rows = []
    for ticker, raw in price_frames.items():
        prices = raw.set_index("Date")[["Open", "Close"]].sort_index()
        starts = [
            score[ticker].first_valid_index()
            for score in scores.values()
        ]
        if any(start is None for start in starts):
            continue
        start = max(starts)
        prices = prices.loc[start:]
        benchmark = buy_and_hold(prices, config=config)
        family_results = {}
        for family, family_scores in scores.items():
            targets = score_to_targets(family_scores[ticker].dropna(), prices.index)
            result = simulate(family, prices, targets, config=config)
            metrics = performance_metrics(result, benchmark)
            metrics.update(_predictive_metrics(family_scores[ticker], prices["Close"]))
            family_results[family] = metrics
        rows.append({"ticker": ticker, "families": family_results})
    return {
        "report_version": "2026.07-v2",
        "universe_version": UNIVERSE_VERSION,
        "data_source": data_source or {
            "mode": "CALLER_PROVIDED",
            "reproducible": False,
        },
        "research_scope": {
            "selection_rule": "pre-fixed; no threshold fitting",
            "interpretation": (
                "screening evidence only; not an OOS model adoption result"
            ),
            "survivorship": (
                "current fixed 55-ticker universe; bias remains"
            ),
        },
        "method": {
            "frequency": "month-end signal, next trading-day open execution",
            "exposure_rule": "score >=60: 100%, >=40: 50%, otherwise cash",
            "participation": "60% market breadth + 40% direction-confirmed volume rank",
            "trend_relative_strength": "50% 12-1 cross-sectional momentum + 50% 200DMA distance",
            "risk": "50% inverse downside-volatility rank + 50% drawdown resilience",
            "business": (
                "PIT_CORPUS_AVAILABLE_NOT_JOINED_TO_PRICE_UNIVERSE"
            ),
        },
        "summary": {family: _summary(rows, family) for family in FAMILIES},
        "business": {
            "status": "BLOCKED_INTEGRATION_NOT_READY",
            "reason": (
                "SEC PIT corpus exists, but entity-period observations are "
                "not yet joined to this price universe and fold contract"
            ),
        },
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


def run_snapshot(snapshot_dir: Path) -> dict:
    frames, manifest = load_snapshot(snapshot_dir)
    report = evaluate(
        frames,
        data_source={
            "mode": "IMMUTABLE_PRICE_SNAPSHOT",
            "reproducible": True,
            "snapshot_id": manifest["snapshot_id"],
            "snapshot_sha256": manifest["snapshot_sha256"],
            "coverage": manifest["coverage"],
            "provider": manifest["source"]["provider"],
            "auto_adjust": manifest["source"]["auto_adjust"],
        },
    )
    report["failures"] = manifest["failures"]
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--period", default="10y")
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = (
        run_snapshot(args.snapshot)
        if args.snapshot
        else run(args.period)
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
