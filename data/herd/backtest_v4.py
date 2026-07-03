"""
herd/backtest_v4.py — HERD v4 보정 승수 검증 스크립트

v3 기본 HERD 시계열에 EPS 서프라이즈 승수와 섹터 상대 강도 승수를 곱해
v4 점수의 수익률/MDD/Rush 신호 변화를 비교한다.

주의:
  Finnhub 무료 tier는 장기 시점별 EPS 컨센서스 복원이 제한적이다.
  따라서 이 스크립트는 현재 계산 가능한 승수를 최근 3년 HERD 시계열에
  동일 적용하는 보수적 sanity check로 사용한다.
"""

import sys
import logging
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from collectors.finnhub_collector import get_eps_surprise_multiplier  # noqa: E402
from collectors.sector_collector import get_sector_multiplier         # noqa: E402
from collectors.stock_collector import collect                        # noqa: E402
from herd.backtest import _build_herd_series                          # noqa: E402
from herd.backtest_v3 import _run_strategy_b                          # noqa: E402

TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "IONQ", "PLTR", "SPY"]
DATA_PERIOD = "3y"
RUSH_THRESHOLD = 75.0
FORWARD_DAYS = 20


def _close_series(df: pd.DataFrame) -> pd.Series:
    """일봉 DataFrame에서 Close 시계열을 추출한다."""
    close = df["Close"].copy()
    close.index = pd.to_datetime(close.index)
    return close.dropna()


def _apply_v4_multiplier(herd: pd.Series, eps: float, sector: float) -> pd.Series:
    """v3 HERD 시계열에 v4 승수를 적용한다."""
    return (herd * eps * sector).clip(lower=0, upper=100).round(2)


def _rush_accuracy(close: pd.Series, herd: pd.Series) -> float | None:
    """
    Rush 이후 20거래일 수익률이 0% 이하인 비율.
    과열 신호가 단기 조정으로 이어졌는지를 보는 보조 지표다.
    """
    aligned = pd.concat([close.rename("close"), herd.rename("herd")], axis=1).dropna()
    rush_rows = aligned[aligned["herd"] >= RUSH_THRESHOLD]
    if rush_rows.empty:
        return None

    outcomes: list[bool] = []
    for dt, row in rush_rows.iterrows():
        pos = aligned.index.get_loc(dt)
        if pos + FORWARD_DAYS >= len(aligned):
            continue
        future = float(aligned["close"].iloc[pos + FORWARD_DAYS])
        current = float(row["close"])
        outcomes.append((future / current - 1) <= 0)

    if not outcomes:
        return None
    return round(sum(outcomes) / len(outcomes) * 100, 1)


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:+.1f}%"


def run_one(ticker: str) -> dict:
    """단일 티커 v3/v4 비교 결과를 반환한다."""
    df = collect(ticker, period=DATA_PERIOD)
    close = _close_series(df)
    herd_v3 = _build_herd_series(df).reindex(close.index).ffill()

    eps_multiplier = get_eps_surprise_multiplier(ticker)
    sector_multiplier = get_sector_multiplier(ticker)
    herd_v4 = _apply_v4_multiplier(herd_v3, eps_multiplier, sector_multiplier)

    v3_result = _run_strategy_b(close, herd_v3)
    v4_result = _run_strategy_b(close, herd_v4)
    preservation = (
        v4_result.return_pct() / v3_result.return_pct() * 100
        if v3_result.return_pct() != 0 else None
    )

    return {
        "ticker": ticker,
        "eps": eps_multiplier,
        "sector": sector_multiplier,
        "v3_return": v3_result.return_pct(),
        "v4_return": v4_result.return_pct(),
        "preservation": preservation,
        "v3_mdd": v3_result.mdd(),
        "v4_mdd": v4_result.mdd(),
        "v3_rush_accuracy": _rush_accuracy(close, herd_v3),
        "v4_rush_accuracy": _rush_accuracy(close, herd_v4),
    }


def main() -> None:
    print("HERD v4 보정 승수 검증")
    print(f"대상: {', '.join(TICKERS)} | 기간: {DATA_PERIOD}")
    print("주의: 현재 승수를 3년 HERD 시계열에 적용한 sanity check입니다.\n")
    header = (
        "Ticker | EPS× | Sector× | v3 Return | v4 Return | 보존율 | "
        "v3 MDD | v4 MDD | v3 Rush Acc | v4 Rush Acc"
    )
    print(header)
    print("-" * len(header))

    for ticker in TICKERS:
        try:
            row = run_one(ticker)
            print(
                f"{row['ticker']:>6} | "
                f"{row['eps']:.2f} | "
                f"{row['sector']:.2f} | "
                f"{_fmt_pct(row['v3_return']):>9} | "
                f"{_fmt_pct(row['v4_return']):>9} | "
                f"{_fmt_pct(row['preservation']):>6} | "
                f"{_fmt_pct(row['v3_mdd']):>6} | "
                f"{_fmt_pct(row['v4_mdd']):>6} | "
                f"{_fmt_pct(row['v3_rush_accuracy']):>11} | "
                f"{_fmt_pct(row['v4_rush_accuracy']):>11}"
            )
        except Exception as e:
            print(f"{ticker:>6} | 계산 실패: {e}")


if __name__ == "__main__":
    main()
