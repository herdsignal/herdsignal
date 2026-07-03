"""
herd/backtest_v5_volatility.py — HERD v5 후보: 변동성 레이어 검증

v4 운영 점수는 변경하지 않고, v3 기본 HERD 시계열에 VIX/VXN/종목별
실현변동성 백분위수 기반 승수를 적용해 v5 후보 성능을 비교한다.

검증 목적:
  - Buy & Hold 대비 HERD 전략을 쓸 이유가 있는지 확인
  - 4년/10년 데이터 중 어떤 기간이 장기투자자 의사결정에 더 적합한지 비교
  - 변동성 레이어가 수익률, MDD, 액션 수, 점수/신호에 주는 영향을 분리해 확인
"""

import logging
import math
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from collectors.stock_collector import collect                         # noqa: E402
from config.settings import (                                          # noqa: E402
    REALIZED_VOL_WINDOW_DAYS,
    VOLATILITY_LAYER_WEIGHTS,
    VOLATILITY_LOOKBACK_DAYS,
    VOLATILITY_MIN_DAYS,
    VOLATILITY_MULTIPLIERS,
)
from herd.backtest import _build_herd_series                           # noqa: E402
from herd.backtest_v3 import _run_strategy_a, _run_strategy_b           # noqa: E402
from herd.backtest_v4 import (                                         # noqa: E402
    _action_counts,
    _fmt_num,
    _fmt_pct,
    _raw_signal,
    _score_impact,
    _stage,
)


TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "IONQ"]
PERIODS = ["4y", "10y"]
MARKET_VOL_TICKERS = {
    "vix": "^VIX",
    "vxn": "^VXN",
}


def _close_series(df: pd.DataFrame) -> pd.Series:
    """일봉 DataFrame에서 날짜 인덱스 Close 시계열을 추출한다."""
    close = df["Close"].copy()
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]
    if "Date" in df.columns:
        close.index = pd.to_datetime(df["Date"])
    else:
        close.index = pd.to_datetime(close.index)
    return close.sort_index().dropna()


def _rolling_percentile(series: pd.Series) -> pd.Series:
    """
    현재 값이 직전 1년 분포에서 어느 백분위인지 계산한다.
    100에 가까울수록 해당 값이 역사적으로 높은 상태다.
    """
    clean = series.astype(float).replace([np.inf, -np.inf], np.nan).dropna()

    def percentile(values: np.ndarray) -> float:
        current = values[-1]
        valid = values[~np.isnan(values)]
        if len(valid) < VOLATILITY_MIN_DAYS or math.isnan(current):
            return np.nan
        return float((valid <= current).sum() / len(valid) * 100)

    return clean.rolling(
        window=VOLATILITY_LOOKBACK_DAYS,
        min_periods=VOLATILITY_MIN_DAYS,
    ).apply(percentile, raw=True)


def _realized_vol_percentile(close: pd.Series) -> pd.Series:
    """20거래일 실현변동성의 1년 백분위수를 계산한다."""
    returns = close.pct_change()
    realized = returns.rolling(REALIZED_VOL_WINDOW_DAYS).std() * math.sqrt(252)
    return _rolling_percentile(realized)


def _market_vol_percentiles(period: str) -> dict[str, pd.Series]:
    """VIX/VXN 백분위수 시계열을 수집한다."""
    percentiles: dict[str, pd.Series] = {}
    for key, ticker in MARKET_VOL_TICKERS.items():
        try:
            df = collect(ticker, period=period)
            percentiles[key] = _rolling_percentile(_close_series(df))
        except Exception as e:
            print(f"  [{ticker}] 변동성 지수 수집 실패: {e}")
            percentiles[key] = pd.Series(dtype=float)
    return percentiles


def _volatility_score(
    close: pd.Series,
    market_percentiles: dict[str, pd.Series],
) -> pd.Series:
    """
    종목 실현변동성 + 시장 변동성(VIX/VXN)을 합성한다.
    점수가 높을수록 공포/불확실성이 큰 변동성 레짐이다.
    """
    realized = _realized_vol_percentile(close)
    pieces = [
        realized.rename("realized"),
        market_percentiles.get("vix", pd.Series(dtype=float)).rename("vix"),
        market_percentiles.get("vxn", pd.Series(dtype=float)).rename("vxn"),
    ]
    aligned = pd.concat(pieces, axis=1).reindex(close.index).ffill()

    weighted_sum = pd.Series(0.0, index=aligned.index)
    weight_sum = pd.Series(0.0, index=aligned.index)
    for key, weight in VOLATILITY_LAYER_WEIGHTS.items():
        values = aligned[key]
        valid = values.notna()
        weighted_sum.loc[valid] += values.loc[valid] * weight
        weight_sum.loc[valid] += weight

    score = weighted_sum / weight_sum.replace(0, np.nan)
    return score.clip(lower=0, upper=100)


def _volatility_multiplier(score: float) -> float:
    """
    변동성 백분위수를 HERD 점수 승수로 변환한다.
    높은 변동성은 공포 쪽으로, 낮은 변동성은 안도/과열 쪽으로 점수를 민다.
    """
    if pd.isna(score):
        return VOLATILITY_MULTIPLIERS["neutral"]
    if score >= 80:
        return VOLATILITY_MULTIPLIERS["extreme_fear"]
    if score >= 60:
        return VOLATILITY_MULTIPLIERS["fear"]
    if score <= 20:
        return VOLATILITY_MULTIPLIERS["complacent"]
    if score <= 40:
        return VOLATILITY_MULTIPLIERS["calm"]
    return VOLATILITY_MULTIPLIERS["neutral"]


def _apply_volatility_layer(herd: pd.Series, vol_score: pd.Series) -> pd.Series:
    """HERD 시계열에 변동성 레이어 승수를 적용한다."""
    multiplier = vol_score.reindex(herd.index).ffill().map(_volatility_multiplier)
    return (herd * multiplier).clip(lower=0, upper=100).round(2)


def _return_capture(strategy_return: float, buyhold_return: float) -> float | None:
    """Buy & Hold 수익률 대비 전략 수익률 보존율."""
    if buyhold_return == 0:
        return None
    return strategy_return / buyhold_return * 100


def _result_row(ticker: str, period: str, market_percentiles: dict[str, pd.Series]) -> dict:
    """단일 티커/기간의 v4 base vs v5 후보 비교 결과를 만든다."""
    df = collect(ticker, period=period)
    close = _close_series(df)

    herd_base = _build_herd_series(df).reindex(close.index).ffill()
    vol_score = _volatility_score(close, market_percentiles)
    herd_v5 = _apply_volatility_layer(herd_base, vol_score)

    buyhold = _run_strategy_a(close)
    base = _run_strategy_b(close, herd_base)
    v5 = _run_strategy_b(close, herd_v5)
    impact = _score_impact(herd_base, herd_v5)
    base_actions = _action_counts(herd_base)
    v5_actions = _action_counts(herd_v5)

    aligned_vol = vol_score.reindex(close.index).dropna()
    last_score = float(herd_v5.dropna().iloc[-1]) if not herd_v5.dropna().empty else None
    last_base = float(herd_base.dropna().iloc[-1]) if not herd_base.dropna().empty else None

    return {
        "ticker": ticker,
        "period": period,
        "start": close.index[0].strftime("%Y-%m-%d"),
        "end": close.index[-1].strftime("%Y-%m-%d"),
        "days": len(close),
        "last_base": last_base,
        "last_v5": last_score,
        "last_stage_base": _stage(last_base) if last_base is not None else "—",
        "last_stage_v5": _stage(last_score) if last_score is not None else "—",
        "last_signal_base": _raw_signal(last_base) if last_base is not None else "—",
        "last_signal_v5": _raw_signal(last_score) if last_score is not None else "—",
        "avg_vol_score": round(float(aligned_vol.mean()), 1) if not aligned_vol.empty else None,
        "high_vol_days": int((aligned_vol >= 80).sum()) if not aligned_vol.empty else 0,
        "low_vol_days": int((aligned_vol <= 20).sum()) if not aligned_vol.empty else 0,
        **impact,
        "buyhold_return": buyhold.return_pct(),
        "base_return": base.return_pct(),
        "v5_return": v5.return_pct(),
        "base_capture": _return_capture(base.return_pct(), buyhold.return_pct()),
        "v5_capture": _return_capture(v5.return_pct(), buyhold.return_pct()),
        "return_delta": v5.return_pct() - base.return_pct(),
        "buyhold_mdd": buyhold.mdd(),
        "base_mdd": base.mdd(),
        "v5_mdd": v5.mdd(),
        "mdd_delta": v5.mdd() - base.mdd(),
        "base_actions": sum(base_actions.values()),
        "v5_actions": sum(v5_actions.values()),
        "base_buy": base_actions["BUY"] + base_actions["ADD"],
        "v5_buy": v5_actions["BUY"] + v5_actions["ADD"],
        "base_sell": base_actions["SELL"] + base_actions["REDUCE"],
        "v5_sell": v5_actions["SELL"] + v5_actions["REDUCE"],
    }


def _avg(rows: list[dict], key: str) -> float | None:
    values = [row[key] for row in rows if row.get(key) is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _print_period(period: str, rows: list[dict]) -> None:
    """기간별 결과를 테이블로 출력한다."""
    print()
    print("=" * 120)
    print(f"HERD v5 후보 비교 — 기간 {period}")
    print("=" * 120)

    print("\n1) 수익률 / MDD 비교")
    header = (
        "Ticker | BuyHold Ret | Base Ret | v5 Ret | v5-Base | "
        "Base Cap | v5 Cap | BuyHold MDD | Base MDD | v5 MDD | ΔMDD"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['ticker']:>6} | "
            f"{_fmt_pct(row['buyhold_return']):>11} | "
            f"{_fmt_pct(row['base_return']):>8} | "
            f"{_fmt_pct(row['v5_return']):>7} | "
            f"{_fmt_pct(row['return_delta']):>7} | "
            f"{_fmt_pct(row['base_capture']):>8} | "
            f"{_fmt_pct(row['v5_capture']):>6} | "
            f"{_fmt_pct(row['buyhold_mdd']):>11} | "
            f"{_fmt_pct(row['base_mdd']):>8} | "
            f"{_fmt_pct(row['v5_mdd']):>6} | "
            f"{_fmt_pct(row['mdd_delta']):>5}"
        )

    print("\n2) 점수 / 신호 영향")
    header = (
        "Ticker | Last Base | Last v5 | Stage | Signal | Avg Vol | "
        "HighVol | LowVol | Avg Δ | Stage 변경 | Signal 변경"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['ticker']:>6} | "
            f"{_fmt_num(row['last_base'], 1):>9} | "
            f"{_fmt_num(row['last_v5'], 1):>7} | "
            f"{row['last_stage_base']}→{row['last_stage_v5']:<7} | "
            f"{row['last_signal_base']}→{row['last_signal_v5']:<6} | "
            f"{_fmt_num(row['avg_vol_score'], 1):>7} | "
            f"{row['high_vol_days']:>7} | "
            f"{row['low_vol_days']:>6} | "
            f"{row['avg_delta']:+.2f} | "
            f"{row['stage_changes']:>4}일 ({_fmt_num(row['stage_change_pct'], 1)}%) | "
            f"{row['signal_changes']:>4}일 ({_fmt_num(row['signal_change_pct'], 1)}%)"
        )

    print("\n3) 실제 액션 수 (20거래일 쿨다운)")
    header = "Ticker | Base Actions | v5 Actions | Base Buy | v5 Buy | Base Sell | v5 Sell"
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['ticker']:>6} | "
            f"{row['base_actions']:>12} | "
            f"{row['v5_actions']:>10} | "
            f"{row['base_buy']:>8} | "
            f"{row['v5_buy']:>6} | "
            f"{row['base_sell']:>9} | "
            f"{row['v5_sell']:>7}"
        )

    print("\n4) 기간 평균")
    print(f"- Buy & Hold 평균 수익률: {_fmt_pct(_avg(rows, 'buyhold_return'))}")
    print(f"- Base HERD 평균 수익률: {_fmt_pct(_avg(rows, 'base_return'))}")
    print(f"- v5 후보 평균 수익률: {_fmt_pct(_avg(rows, 'v5_return'))}")
    print(f"- v5 후보 평균 수익률 변화: {_fmt_pct(_avg(rows, 'return_delta'))}")
    print(f"- Buy & Hold 평균 MDD: {_fmt_pct(_avg(rows, 'buyhold_mdd'))}")
    print(f"- Base HERD 평균 MDD: {_fmt_pct(_avg(rows, 'base_mdd'))}")
    print(f"- v5 후보 평균 MDD: {_fmt_pct(_avg(rows, 'v5_mdd'))}")
    print(f"- v5 후보 평균 MDD 변화: {_fmt_pct(_avg(rows, 'mdd_delta'))}")
    print(f"- 평균 단계 변경률: {_fmt_num(_avg(rows, 'stage_change_pct'), 1)}%")
    print(f"- 평균 신호 변경률: {_fmt_num(_avg(rows, 'signal_change_pct'), 1)}%")


def _print_period_recommendation(all_rows: dict[str, list[dict]]) -> None:
    """4년 vs 10년 사용 판단을 출력한다."""
    print()
    print("=" * 120)
    print("기간 선택 판단")
    print("=" * 120)
    header = "Period | Avg BuyHold | Avg Base | Avg v5 | Avg v5-Base | Avg v5 MDD | Avg Signal Change"
    print(header)
    print("-" * len(header))
    for period, rows in all_rows.items():
        print(
            f"{period:>6} | "
            f"{_fmt_pct(_avg(rows, 'buyhold_return')):>11} | "
            f"{_fmt_pct(_avg(rows, 'base_return')):>8} | "
            f"{_fmt_pct(_avg(rows, 'v5_return')):>7} | "
            f"{_fmt_pct(_avg(rows, 'return_delta')):>11} | "
            f"{_fmt_pct(_avg(rows, 'v5_mdd')):>10} | "
            f"{_fmt_num(_avg(rows, 'signal_change_pct'), 1):>16}%"
        )

    print()
    print("해석:")
    print("- 10년은 여러 시장 국면을 더 많이 담지만, IONQ처럼 상장 기간이 짧은 종목은 사실상 짧은 표본으로 계산된다.")
    print("- 4년은 현재 시장 구조와 최근 금리/AI 사이클을 더 잘 반영하지만, 코로나 이후 상승장 편향이 남을 수 있다.")
    print("- 운영 기본값은 5년을 유지하고, v5 검증은 4년과 10년을 모두 통과해야 채택하는 방식이 가장 안전하다.")


def main() -> None:
    print("HERD v5 후보 — Volatility Layer 백테스트")
    print(f"대상: {', '.join(TICKERS)}")
    print(f"기간: {', '.join(PERIODS)}")
    print("Base HERD는 기존 점수 기반 전략, v5 후보는 VIX/VXN/실현변동성 승수 적용 전략입니다.")

    all_rows: dict[str, list[dict]] = {}
    for period in PERIODS:
        print(f"\n[{period}] 시장 변동성 데이터 수집 중...")
        market_percentiles = _market_vol_percentiles(period)
        rows: list[dict] = []
        for ticker in TICKERS:
            try:
                print(f"  [{ticker}] 계산 중...", end=" ", flush=True)
                row = _result_row(ticker, period, market_percentiles)
                rows.append(row)
                print(
                    f"완료 | Base {_fmt_pct(row['base_return'])} → "
                    f"v5 {_fmt_pct(row['v5_return'])}"
                )
            except Exception as e:
                print(f"실패: {e}")
        all_rows[period] = rows
        if rows:
            _print_period(period, rows)

    if all_rows:
        _print_period_recommendation(all_rows)


if __name__ == "__main__":
    main()
