"""
signal_reliability.py — HERD 신호 신뢰도 계산

저장된 herd_scores 시계열과 yfinance 가격 데이터를 결합해
Flee/Rush 신호가 실제로 장기투자 행동에 도움이 됐는지 요약한다.
DB 스키마를 변경하지 않는 on-demand 분석용 모듈이다.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf
from sqlalchemy import select

DATA_ROOT = Path(__file__).resolve().parents[1]
if str(DATA_ROOT) not in sys.path:
    sys.path.insert(0, str(DATA_ROOT))

from config.database import create_db_engine, get_session_factory
from config.settings import HERD_THRESHOLDS
from init_db import HerdScore

logger = logging.getLogger(__name__)

BUY_SCORE = 40
SELL_SCORE = 60
FLEE_FORWARD_DAYS = 126
RUSH_FORWARD_DAYS = 63
SIGNAL_COOLDOWN_DAYS = 20
RUSH_DRAWDOWN_HIT_PCT = -5.0
BUY_FORWARD_WINDOWS = {
    "buy_return_1m": 21,
    "buy_return_3m": 63,
    "buy_return_6m": 126,
}
SELL_FORWARD_WINDOWS = {
    "sell_drawdown_1m": 21,
    "sell_drawdown_3m": 63,
}


def calculate_signal_reliability(ticker: str, years: int = 3) -> dict[str, Any]:
    """티커별 HERD 신호 신뢰도 요약을 반환한다."""
    ticker = ticker.upper().strip()
    if not ticker:
        raise ValueError("ticker is required")

    start_date = date.today() - timedelta(days=365 * years + 30)
    scores = _load_scores(ticker, start_date)
    if len(scores) < 2:
        return _limited_response(ticker, years, len(scores), "HERD 히스토리 표본 부족")

    close = _fetch_close_prices(ticker, years)
    if close.empty or len(close) < 60:
        return _limited_response(ticker, years, len(scores), "가격 히스토리 표본 부족")

    score_frame = _build_score_frame(scores)
    signal_stats = _measure_signal_hits(score_frame, close)
    strategy_stats = _simulate_action_layer(score_frame, close)

    grade, label, summary = _grade_reliability(
        history_count=len(score_frame),
        signal_stats=signal_stats,
        strategy_stats=strategy_stats,
    )

    return _json_safe({
        "ticker": ticker,
        "model_version": "HERD_signal_reliability_v1",
        "period_years": years,
        "history_count": len(score_frame),
        "flee_sample_size": signal_stats["flee_sample_size"],
        "flee_hit_rate": signal_stats["flee_hit_rate"],
        "rush_sample_size": signal_stats["rush_sample_size"],
        "rush_hit_rate": signal_stats["rush_hit_rate"],
        "buy_return_1m": signal_stats["buy_return_1m"],
        "buy_return_3m": signal_stats["buy_return_3m"],
        "buy_return_6m": signal_stats["buy_return_6m"],
        "sell_drawdown_1m": signal_stats["sell_drawdown_1m"],
        "sell_drawdown_3m": signal_stats["sell_drawdown_3m"],
        "mdd_improvement": strategy_stats["mdd_improvement"],
        "return_preservation": strategy_stats["return_preservation"],
        "annual_actions": strategy_stats["annual_actions"],
        "strategy_return": strategy_stats["strategy_return"],
        "buy_hold_return": strategy_stats["buy_hold_return"],
        "strategy_mdd": strategy_stats["strategy_mdd"],
        "buy_hold_mdd": strategy_stats["buy_hold_mdd"],
        "reliability_grade": grade,
        "reliability_label": label,
        "summary": summary,
        "last_updated": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    })


def _load_scores(ticker: str, start_date: date) -> list[HerdScore]:
    engine = create_db_engine()
    session_factory = get_session_factory(engine)
    with session_factory() as session:
        stmt = (
            select(HerdScore)
            .where(HerdScore.ticker == ticker)
            .where(HerdScore.score_date >= start_date)
            .order_by(HerdScore.score_date.asc())
        )
        return list(session.execute(stmt).scalars())


def _fetch_close_prices(ticker: str, years: int) -> pd.Series:
    period_years = max(years + 1, 4)
    raw = yf.download(
        ticker,
        period=f"{period_years}y",
        interval="1d",
        auto_adjust=True,
        progress=False,
    )
    if raw is None or raw.empty:
        return pd.Series(dtype=float)

    close = raw["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close = close.dropna().astype(float)
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    return close.sort_index()


def _build_score_frame(scores: list[HerdScore]) -> pd.DataFrame:
    rows = [
        {
            "date": pd.Timestamp(score.score_date),
            "score": float(score.herd_score),
            "stage": score.herd_stage,
            "signal": score.signal,
        }
        for score in scores
    ]
    frame = pd.DataFrame(rows).drop_duplicates(subset=["date"], keep="last")
    return frame.sort_values("date").reset_index(drop=True)


def _measure_signal_hits(score_frame: pd.DataFrame, close: pd.Series) -> dict[str, Any]:
    flee_hits: list[bool] = []
    rush_hits: list[bool] = []
    buy_forward_returns: dict[str, list[float]] = {key: [] for key in BUY_FORWARD_WINDOWS}
    sell_forward_drawdowns: dict[str, list[float]] = {key: [] for key in SELL_FORWARD_WINDOWS}
    last_flee_date: pd.Timestamp | None = None
    last_rush_date: pd.Timestamp | None = None

    for row in score_frame.itertuples(index=False):
        score_date = pd.Timestamp(row.date)
        score = float(row.score)

        if score <= BUY_SCORE:
            if _inside_cooldown(score_date, last_flee_date):
                continue
            ret = _forward_return(close, score_date, FLEE_FORWARD_DAYS)
            if ret is None:
                continue
            flee_hits.append(ret > 0)
            for key, days in BUY_FORWARD_WINDOWS.items():
                window_ret = _forward_return(close, score_date, days)
                if window_ret is not None:
                    buy_forward_returns[key].append(window_ret)
            last_flee_date = score_date

        if score >= SELL_SCORE:
            if _inside_cooldown(score_date, last_rush_date):
                continue
            ret = _forward_return(close, score_date, RUSH_FORWARD_DAYS)
            drawdown = _forward_drawdown(close, score_date, RUSH_FORWARD_DAYS)
            if ret is None or drawdown is None:
                continue
            rush_hits.append(ret < 0 or drawdown <= RUSH_DRAWDOWN_HIT_PCT)
            for key, days in SELL_FORWARD_WINDOWS.items():
                window_drawdown = _forward_drawdown(close, score_date, days)
                if window_drawdown is not None:
                    sell_forward_drawdowns[key].append(window_drawdown)
            last_rush_date = score_date

    return {
        "flee_sample_size": len(flee_hits),
        "flee_hit_rate": _rate(flee_hits),
        "rush_sample_size": len(rush_hits),
        "rush_hit_rate": _rate(rush_hits),
        **{key: _average(values) for key, values in buy_forward_returns.items()},
        **{key: _average(values) for key, values in sell_forward_drawdowns.items()},
    }


def _simulate_action_layer(score_frame: pd.DataFrame, close: pd.Series) -> dict[str, Any]:
    if close.empty or score_frame.empty:
        return _empty_strategy_stats()

    score_series = pd.Series(
        score_frame["score"].to_numpy(),
        index=pd.to_datetime(score_frame["date"]).dt.normalize(),
    )
    score_series = score_series[~score_series.index.duplicated(keep="last")]
    aligned_scores = score_series.reindex(close.index, method="ffill")
    aligned_scores = aligned_scores.dropna()
    if aligned_scores.empty:
        return _empty_strategy_stats()

    close = close.loc[aligned_scores.index]
    cash = 0.0
    shares = 10_000.0 / float(close.iloc[0])
    initial_value = 10_000.0
    values: list[float] = []
    actions = 0
    last_action_index = -SIGNAL_COOLDOWN_DAYS

    for idx, (price_date, price) in enumerate(close.items()):
        score = float(aligned_scores.loc[price_date])
        value_before = cash + shares * price

        if idx - last_action_index >= SIGNAL_COOLDOWN_DAYS:
            if score >= HERD_THRESHOLDS["rush"] and shares > 0:
                sell_value = value_before * 0.15
                sell_shares = min(shares, sell_value / price)
                shares -= sell_shares
                cash += sell_shares * price
                actions += 1
                last_action_index = idx
            elif score >= SELL_SCORE and shares > 0:
                sell_value = value_before * 0.05
                sell_shares = min(shares, sell_value / price)
                shares -= sell_shares
                cash += sell_shares * price
                actions += 1
                last_action_index = idx
            elif score <= HERD_THRESHOLDS["flee"] and cash > 0:
                buy_value = min(cash, value_before * 0.22)
                shares += buy_value / price
                cash -= buy_value
                actions += 1
                last_action_index = idx
            elif score <= BUY_SCORE and cash > 0:
                buy_value = min(cash, value_before * 0.04)
                shares += buy_value / price
                cash -= buy_value
                actions += 1
                last_action_index = idx

        values.append(cash + shares * price)

    strategy = pd.Series(values, index=close.index)
    buy_hold = initial_value * (close / float(close.iloc[0]))

    strategy_return = (float(strategy.iloc[-1]) / initial_value - 1) * 100
    buy_hold_return = (float(buy_hold.iloc[-1]) / initial_value - 1) * 100
    strategy_mdd = _max_drawdown(strategy)
    buy_hold_mdd = _max_drawdown(buy_hold)
    return_preservation = None
    if buy_hold_return > 0:
        return_preservation = max(0.0, strategy_return / buy_hold_return * 100)

    elapsed_years = max((close.index[-1] - close.index[0]).days / 365.25, 0.25)

    return {
        "strategy_return": strategy_return,
        "buy_hold_return": buy_hold_return,
        "strategy_mdd": strategy_mdd,
        "buy_hold_mdd": buy_hold_mdd,
        "mdd_improvement": abs(buy_hold_mdd) - abs(strategy_mdd),
        "return_preservation": return_preservation,
        "annual_actions": actions / elapsed_years,
    }


def _forward_return(close: pd.Series, signal_date: pd.Timestamp, days: int) -> float | None:
    start_idx = close.index.searchsorted(signal_date)
    end_idx = start_idx + days
    if start_idx >= len(close) or end_idx >= len(close):
        return None
    start = float(close.iloc[start_idx])
    end = float(close.iloc[end_idx])
    if start <= 0:
        return None
    return (end / start - 1) * 100


def _forward_drawdown(close: pd.Series, signal_date: pd.Timestamp, days: int) -> float | None:
    start_idx = close.index.searchsorted(signal_date)
    end_idx = start_idx + days
    if start_idx >= len(close) or end_idx >= len(close):
        return None
    window = close.iloc[start_idx : end_idx + 1]
    if window.empty:
        return None
    start = float(window.iloc[0])
    low = float(window.min())
    if start <= 0:
        return None
    return (low / start - 1) * 100


def _max_drawdown(values: pd.Series) -> float:
    peak = values.cummax()
    drawdown = (values / peak - 1) * 100
    return float(drawdown.min())


def _inside_cooldown(current: pd.Timestamp, previous: pd.Timestamp | None) -> bool:
    if previous is None:
        return False
    return (current - previous).days < SIGNAL_COOLDOWN_DAYS


def _rate(values: list[bool]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values) * 100


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _grade_reliability(
    history_count: int,
    signal_stats: dict[str, Any],
    strategy_stats: dict[str, Any],
) -> tuple[str, str, str]:
    total_samples = signal_stats["flee_sample_size"] + signal_stats["rush_sample_size"]
    if history_count < 12 or total_samples < 3:
        return ("DATA_LIMITED", "표본 부족", "신호 표본이 적어 참고용으로만 봐야 합니다.")

    score = 0
    flee_hit_rate = signal_stats["flee_hit_rate"]
    rush_hit_rate = signal_stats["rush_hit_rate"]
    mdd_improvement = strategy_stats["mdd_improvement"]
    return_preservation = strategy_stats["return_preservation"]
    annual_actions = strategy_stats["annual_actions"]

    if flee_hit_rate is not None and flee_hit_rate >= 60:
        score += 25
    if rush_hit_rate is not None and rush_hit_rate >= 55:
        score += 25
    if mdd_improvement is not None and mdd_improvement >= 3:
        score += 20
    if return_preservation is not None and return_preservation >= 60:
        score += 20
    if 2 <= annual_actions <= 12:
        score += 10

    if score >= 80:
        return ("STRONG", "신뢰 높음", "과거 신호가 수익 보존과 낙폭 관리에 모두 유효했습니다.")
    if score >= 60:
        return ("GOOD", "참고 가능", "과거 신호가 일부 구간에서 유효했습니다.")
    return ("WATCH", "주의", "과거 성과가 충분히 강하지 않아 보조 지표로 봐야 합니다.")


def _empty_strategy_stats() -> dict[str, Any]:
    return {
        "strategy_return": None,
        "buy_hold_return": None,
        "strategy_mdd": None,
        "buy_hold_mdd": None,
        "mdd_improvement": None,
        "return_preservation": None,
        "annual_actions": None,
    }


def _limited_response(ticker: str, years: int, history_count: int, summary: str) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "model_version": "HERD_signal_reliability_v1",
        "period_years": years,
        "history_count": history_count,
        "flee_sample_size": 0,
        "flee_hit_rate": None,
        "rush_sample_size": 0,
        "rush_hit_rate": None,
        "buy_return_1m": None,
        "buy_return_3m": None,
        "buy_return_6m": None,
        "sell_drawdown_1m": None,
        "sell_drawdown_3m": None,
        "mdd_improvement": None,
        "return_preservation": None,
        "annual_actions": None,
        "strategy_return": None,
        "buy_hold_return": None,
        "strategy_mdd": None,
        "buy_hold_mdd": None,
        "reliability_grade": "DATA_LIMITED",
        "reliability_label": "표본 부족",
        "summary": summary,
        "last_updated": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HERD 신호 신뢰도 계산")
    parser.add_argument("ticker", help="티커 심볼")
    parser.add_argument("--years", type=int, default=3, help="분석 기간(년)")
    args = parser.parse_args()

    try:
        result = calculate_signal_reliability(args.ticker, args.years)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        logger.exception("HERD 신호 신뢰도 계산 실패")
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
