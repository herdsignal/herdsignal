"""공통 비교 엔진으로 현재 HERD v4와 Python v6.1 연구 규칙을 재평가한다."""

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
from config.settings import HERD_WEIGHTS
from herd.benchmark_engine import (
    BenchmarkConfig,
    buy_and_hold,
    performance_metrics,
    simulate_fractional_actions,
)
from herd.indicator_inventory import build_v4_indicator_frame
from herd.legacy_action_rules import action_decision, trend_frame
from herd.validation_universe import SECTOR_UNIVERSE, TICKERS, UNIVERSE_VERSION

FLEE = 15.0
SCATTER = 40.0
DRIFT = 60.0
RUSH = 75.0
COOLDOWN = 20


def v4_base_score(frame: pd.DataFrame) -> pd.Series:
    weights = {
        "monthly_rsi": HERD_WEIGHTS["monthly_rsi"],
        "weekly_rsi": HERD_WEIGHTS["weekly_rsi"],
        "position_52w": HERD_WEIGHTS["52w_position"],
        "ma200_deviation": HERD_WEIGHTS["ma200_deviation"],
        "volume_strength": HERD_WEIGHTS["volume_strength"],
        "ma200_weekly": HERD_WEIGHTS["ma200_weekly"],
    }
    score = sum(frame[key] * weight for key, weight in weights.items())
    return score.dropna().clip(0, 100).rename("herd_v4_base")


def _with_cooldown(raw: pd.DataFrame, cooldown: int = COOLDOWN) -> pd.DataFrame:
    result = raw.copy()
    last = {"BUY": -cooldown - 1, "SELL": -cooldown - 1}
    for position in range(len(result)):
        action = str(result.iloc[position]["action"])
        if action not in last:
            continue
        if position - last[action] <= cooldown:
            result.iat[position, result.columns.get_loc("action")] = "HOLD"
            result.iat[position, result.columns.get_loc("ratio")] = 0.0
        else:
            last[action] = position
    return result


def v4_actions(score: pd.Series) -> pd.DataFrame:
    rows = []
    for value in score:
        if value >= RUSH:
            rows.append(("SELL", 0.30, "RUSH"))
        elif value >= DRIFT:
            rows.append(("SELL", 0.05, "DRIFT"))
        elif value <= FLEE:
            rows.append(("BUY", 0.10, "FLEE"))
        elif value <= SCATTER:
            rows.append(("BUY", 0.15, "SCATTER"))
        else:
            rows.append(("HOLD", 0.0, "CALM"))
    return _with_cooldown(pd.DataFrame(rows, index=score.index, columns=["action", "ratio", "regime"]))


def v61_actions(close: pd.Series, score: pd.Series) -> pd.DataFrame:
    context = trend_frame(close).reindex(score.index).ffill()
    rows: list[tuple[str, float, str]] = []
    previous_action = "HOLD"
    action_days = 0
    for date, value in score.items():
        regime, action, ratio = action_decision(float(value), context.loc[date], "v61")
        if action == previous_action:
            action_days += 1
        else:
            previous_action = action
            action_days = 1
        if ratio > 0:
            lifecycle = 0.65 if action_days <= 5 else 1.0 if action_days <= 20 else 0.82 if action_days <= 45 else 0.55
            ratio = round(ratio * lifecycle, 2)
        rows.append((action, ratio, regime))
    return _with_cooldown(pd.DataFrame(rows, index=score.index, columns=["action", "ratio", "regime"]))


def _json_metrics(metrics: dict) -> dict:
    return {
        key: (None if value is None or (isinstance(value, float) and not np.isfinite(value)) else value)
        for key, value in metrics.items()
    }


def evaluate_ticker(ticker: str, period: str = "10y") -> dict:
    raw = collect(ticker, period=period)
    raw["Date"] = pd.to_datetime(raw["Date"])
    prices = raw.set_index("Date")[["Open", "Close"]].sort_index()
    indicators = build_v4_indicator_frame(raw)
    score = v4_base_score(indicators)
    if score.empty:
        raise ValueError("full v4 indicator history unavailable")
    prices = prices.loc[score.index.min():].copy()
    score = score.reindex(prices.index).ffill()
    close = prices["Close"]

    base_config = BenchmarkConfig()
    stress_config = BenchmarkConfig(fee_rate=0.002, slippage_rate=0.0015)
    benchmark = buy_and_hold(prices, config=base_config)
    v4 = simulate_fractional_actions("HERD v4 base", prices, v4_actions(score), config=base_config)
    v61 = simulate_fractional_actions("HERD v6.1 Python", prices, v61_actions(close, score), config=base_config)
    stress_benchmark = buy_and_hold(prices, config=stress_config)
    stress_v4 = simulate_fractional_actions("HERD v4 base stress", prices, v4_actions(score), config=stress_config)
    stress_v61 = simulate_fractional_actions("HERD v6.1 Python stress", prices, v61_actions(close, score), config=stress_config)
    return {
        "ticker": ticker,
        "start": prices.index.min().date().isoformat(),
        "end": prices.index.max().date().isoformat(),
        "observations": len(prices),
        "buy_hold": _json_metrics(performance_metrics(benchmark)),
        "v4": _json_metrics(performance_metrics(v4, benchmark)),
        "v61": _json_metrics(performance_metrics(v61, benchmark)),
        "cost_stress": {
            "v4": _json_metrics(performance_metrics(stress_v4, stress_benchmark)),
            "v61": _json_metrics(performance_metrics(stress_v61, stress_benchmark)),
        },
    }


def _median(rows: list[dict], path: tuple[str, ...]) -> float | None:
    values = []
    for row in rows:
        value = row
        for key in path:
            value = value.get(key) if isinstance(value, dict) else None
        if value is not None:
            values.append(float(value))
    return float(np.median(values)) if values else None


def summarize(rows: list[dict], model: str) -> dict:
    excess = [row[model]["excess_cagr"] for row in rows if row[model]["excess_cagr"] is not None]
    return {
        "successful_tickers": len(rows),
        "median_cagr": _median(rows, (model, "cagr")),
        "median_excess_cagr": _median(rows, (model, "excess_cagr")),
        "positive_excess_rate": sum(value > 0 for value in excess) / len(excess) * 100 if excess else None,
        "median_max_drawdown": _median(rows, (model, "max_drawdown")),
        "median_upside_capture": _median(rows, (model, "upside_capture")),
        "median_downside_capture": _median(rows, (model, "downside_capture")),
        "median_turnover": _median(rows, (model, "turnover")),
        "median_trade_count": _median(rows, (model, "trade_count")),
        "stress_median_excess_cagr": _median(rows, ("cost_stress", model, "excess_cagr")),
    }


def run(period: str = "10y") -> dict:
    rows, failures = [], {}
    for ticker in TICKERS:
        try:
            rows.append(evaluate_ticker(ticker, period))
        except Exception as exc:
            failures[ticker] = str(exc)
    ticker_sector = {
        ticker: sector for sector, tickers in SECTOR_UNIVERSE.items() for ticker in tickers
    }
    sector_summary = {}
    for sector in SECTOR_UNIVERSE:
        subset = [row for row in rows if ticker_sector.get(row["ticker"]) == sector]
        sector_summary[sector] = {
            "v4_median_excess_cagr": _median(subset, ("v4", "excess_cagr")),
            "v61_median_excess_cagr": _median(subset, ("v61", "excess_cagr")),
        }
    return {
        "report_version": "2026.07-v1",
        "universe_version": UNIVERSE_VERSION,
        "period": period,
        "model_scope": {
            "v4": "price-only v4 base; PIT EPS/sector multipliers excluded",
            "v61": "Python research v6.1 reconstruction; not Java production parity",
            "survivorship": "current fixed 55-ticker universe; bias remains",
        },
        "summary": {"v4": summarize(rows, "v4"), "v61": summarize(rows, "v61")},
        "sector_summary": sector_summary,
        "rows": rows,
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--period", default="10y")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run(args.period)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
