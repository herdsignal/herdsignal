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
DRIFT_LOWER = 60.0
SCATTER_UPPER = 40.0
FLEE_THRESHOLD = 15.0
SIGNAL_COOLDOWN = 20
FORWARD_DAYS = 20


def _close_series(df: pd.DataFrame) -> pd.Series:
    """일봉 DataFrame에서 Close 시계열을 추출한다."""
    close = df["Close"].copy()
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]
    if "Date" in df.columns:
        close.index = pd.to_datetime(df["Date"])
    else:
        close.index = pd.to_datetime(close.index)
    return close.dropna()


def _apply_v4_multiplier(herd: pd.Series, eps: float, sector: float) -> pd.Series:
    """v3 HERD 시계열에 v4 승수를 적용한다."""
    return (herd * eps * sector).clip(lower=0, upper=100).round(2)


def _stage(score: float) -> str:
    """HERD 점수를 5단계 라벨로 변환한다."""
    if score >= RUSH_THRESHOLD:
        return "Rush"
    if score >= DRIFT_LOWER:
        return "Drift"
    if score > SCATTER_UPPER:
        return "Calm"
    if score > FLEE_THRESHOLD:
        return "Scatter"
    return "Flee"


def _raw_signal(score: float) -> str:
    """DB 저장 로직과 같은 점수 기반 신호를 반환한다."""
    if score >= RUSH_THRESHOLD:
        return "SELL"
    if score >= DRIFT_LOWER:
        return "REDUCE"
    if score <= FLEE_THRESHOLD:
        return "BUY"
    if score <= SCATTER_UPPER:
        return "ADD"
    return "HOLD"


def _action_counts(herd: pd.Series) -> dict[str, int]:
    """
    전략 B와 동일한 20거래일 동방향 쿨다운을 적용해 실제 액션 횟수를 센다.
    HOLD는 매매 액션이 아니므로 집계하지 않는다.
    """
    counts = {"BUY": 0, "ADD": 0, "REDUCE": 0, "SELL": 0}
    last_sell_pos = -SIGNAL_COOLDOWN - 1
    last_buy_pos = -SIGNAL_COOLDOWN - 1

    for i, score in enumerate(herd.dropna()):
        sell_ok = (i - last_sell_pos) > SIGNAL_COOLDOWN
        buy_ok = (i - last_buy_pos) > SIGNAL_COOLDOWN

        if score >= RUSH_THRESHOLD and sell_ok:
            counts["SELL"] += 1
            last_sell_pos = i
        elif score >= DRIFT_LOWER and sell_ok:
            counts["REDUCE"] += 1
            last_sell_pos = i
        elif score <= FLEE_THRESHOLD and buy_ok:
            counts["BUY"] += 1
            last_buy_pos = i
        elif score <= SCATTER_UPPER and buy_ok:
            counts["ADD"] += 1
            last_buy_pos = i

    return counts


def _score_impact(herd_v3: pd.Series, herd_v4: pd.Series) -> dict:
    """v3와 v4 점수/단계/신호 차이를 요약한다."""
    aligned = pd.concat([herd_v3.rename("v3"), herd_v4.rename("v4")], axis=1).dropna()
    if aligned.empty:
        return {
            "days": 0,
            "avg_delta": None,
            "avg_abs_delta": None,
            "max_abs_delta": None,
            "stage_changes": 0,
            "stage_change_pct": None,
            "signal_changes": 0,
            "signal_change_pct": None,
        }

    delta = aligned["v4"] - aligned["v3"]
    stage_v3 = aligned["v3"].map(_stage)
    stage_v4 = aligned["v4"].map(_stage)
    signal_v3 = aligned["v3"].map(_raw_signal)
    signal_v4 = aligned["v4"].map(_raw_signal)
    stage_changes = int((stage_v3 != stage_v4).sum())
    signal_changes = int((signal_v3 != signal_v4).sum())
    days = len(aligned)

    return {
        "days": days,
        "avg_delta": round(float(delta.mean()), 2),
        "avg_abs_delta": round(float(delta.abs().mean()), 2),
        "max_abs_delta": round(float(delta.abs().max()), 2),
        "stage_changes": stage_changes,
        "stage_change_pct": round(stage_changes / days * 100, 1),
        "signal_changes": signal_changes,
        "signal_change_pct": round(signal_changes / days * 100, 1),
    }


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


def _fmt_num(value: float | int | None, digits: int = 1) -> str:
    if value is None:
        return "—"
    if isinstance(value, int):
        return str(value)
    return f"{value:.{digits}f}"


def _fmt_delta(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:+.2f}"


def _avg(rows: list[dict], key: str) -> float | None:
    values = [row[key] for row in rows if row.get(key) is not None]
    if not values:
        return None
    return sum(values) / len(values)


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
    impact = _score_impact(herd_v3, herd_v4)
    v3_actions = _action_counts(herd_v3)
    v4_actions = _action_counts(herd_v4)
    preservation = (
        v4_result.return_pct() / v3_result.return_pct() * 100
        if v3_result.return_pct() != 0 else None
    )

    return {
        "ticker": ticker,
        "eps": eps_multiplier,
        "sector": sector_multiplier,
        "multiplier": round(eps_multiplier * sector_multiplier, 2),
        **impact,
        "v3_return": v3_result.return_pct(),
        "v4_return": v4_result.return_pct(),
        "return_delta": v4_result.return_pct() - v3_result.return_pct(),
        "preservation": preservation,
        "v3_mdd": v3_result.mdd(),
        "v4_mdd": v4_result.mdd(),
        "mdd_delta": v4_result.mdd() - v3_result.mdd(),
        "v3_rush_accuracy": _rush_accuracy(close, herd_v3),
        "v4_rush_accuracy": _rush_accuracy(close, herd_v4),
        "v3_actions": sum(v3_actions.values()),
        "v4_actions": sum(v4_actions.values()),
        "v3_buy_actions": v3_actions["BUY"] + v3_actions["ADD"],
        "v4_buy_actions": v4_actions["BUY"] + v4_actions["ADD"],
        "v3_sell_actions": v3_actions["SELL"] + v3_actions["REDUCE"],
        "v4_sell_actions": v4_actions["SELL"] + v4_actions["REDUCE"],
    }


def main() -> None:
    print("HERD v4 보정 승수 검증")
    print(f"대상: {', '.join(TICKERS)} | 기간: {DATA_PERIOD}")
    print("주의: 현재 승수를 3년 HERD 시계열에 적용한 sanity check입니다.\n")

    rows: list[dict] = []
    for ticker in TICKERS:
        try:
            rows.append(run_one(ticker))
        except Exception as e:
            print(f"{ticker:>6} | 계산 실패: {e}")

    print("1) 점수/신호 영향")
    header = (
        "Ticker | EPS× | Sector× | Total× | Avg Δ | Avg |Δ| | Max |Δ| | "
        "Stage 변경 | Signal 변경"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['ticker']:>6} | "
            f"{row['eps']:.2f} | "
            f"{row['sector']:.2f} | "
            f"{row['multiplier']:.2f} | "
            f"{_fmt_delta(row['avg_delta']):>6} | "
            f"{_fmt_num(row['avg_abs_delta'], 2):>7} | "
            f"{_fmt_num(row['max_abs_delta'], 2):>7} | "
            f"{row['stage_changes']:>4}일 ({_fmt_num(row['stage_change_pct'])}%) | "
            f"{row['signal_changes']:>4}일 ({_fmt_num(row['signal_change_pct'])}%)"
        )

    print("\n2) 매매 성능")
    header = (
        "Ticker | v3 Return | v4 Return | ΔReturn | 보존율 | "
        "v3 MDD | v4 MDD | ΔMDD | v3 Rush Acc | v4 Rush Acc"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['ticker']:>6} | "
            f"{_fmt_pct(row['v3_return']):>9} | "
            f"{_fmt_pct(row['v4_return']):>9} | "
            f"{_fmt_pct(row['return_delta']):>8} | "
            f"{_fmt_pct(row['preservation']):>6} | "
            f"{_fmt_pct(row['v3_mdd']):>6} | "
            f"{_fmt_pct(row['v4_mdd']):>6} | "
            f"{_fmt_pct(row['mdd_delta']):>5} | "
            f"{_fmt_pct(row['v3_rush_accuracy']):>11} | "
            f"{_fmt_pct(row['v4_rush_accuracy']):>11}"
        )

    print("\n3) 실제 액션 수 (20거래일 쿨다운 적용)")
    header = "Ticker | v3 Actions | v4 Actions | v3 Buy | v4 Buy | v3 Sell | v4 Sell"
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['ticker']:>6} | "
            f"{row['v3_actions']:>10} | "
            f"{row['v4_actions']:>10} | "
            f"{row['v3_buy_actions']:>6} | "
            f"{row['v4_buy_actions']:>6} | "
            f"{row['v3_sell_actions']:>7} | "
            f"{row['v4_sell_actions']:>7}"
        )

    print("\n4) 포트폴리오 평균")
    print(f"- 평균 수익률: v3 {_fmt_pct(_avg(rows, 'v3_return'))} → v4 {_fmt_pct(_avg(rows, 'v4_return'))}")
    print(f"- 평균 MDD: v3 {_fmt_pct(_avg(rows, 'v3_mdd'))} → v4 {_fmt_pct(_avg(rows, 'v4_mdd'))}")
    print(f"- 평균 수익률 보존율: {_fmt_pct(_avg(rows, 'preservation'))}")
    print(f"- 평균 단계 변경률: {_fmt_num(_avg(rows, 'stage_change_pct'))}%")
    print(f"- 평균 신호 변경률: {_fmt_num(_avg(rows, 'signal_change_pct'))}%")


if __name__ == "__main__":
    main()
