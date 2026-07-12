"""
herd/backtest_action_layer.py — HERD Action Layer 사전 검증 백테스트

목적:
  운영 코드에 붙이기 전에 "HERD 점수 + 추세 컨텍스트" 기반 동적 행동 규칙이
  기존 고정 비율 전략 대비 수익률 보존율을 개선하는지 검증한다.

비교:
  A — Buy & Hold
  B — 기존 HERD 고정 비율 (Rush 30% / Drift 5% / Flee 30%)
  D — Action Layer Growth 동적 비율
  E — Action Layer Balanced 동적 비율

주의:
  이 스크립트는 실험용이다. Python 운영 계산, DB 저장, API 응답에는 영향을 주지 않는다.
"""

import logging
import argparse
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from collectors.stock_collector import collect                         # noqa: E402
from herd.backtest import _build_herd_series                           # noqa: E402
from herd.backtest_v3 import (                                         # noqa: E402
    FEE_RATE,
    INITIAL_CASH,
    SIGNAL_COOLDOWN,
    _buy,
    _run_strategy_a,
    _run_strategy_b,
    _sell,
)
from herd.validation_universe import TICKERS as DIVERSE_TICKERS, UNIVERSE_VERSION  # noqa: E402
from config.database import create_db_engine, get_session_factory  # noqa: E402
from init_db import HerdScore  # noqa: E402

_SessionFactory = get_session_factory(create_db_engine())


SMOKE_TICKERS = ["NVDA", "MSFT", "AAPL", "JPM", "SPY"]
DATA_PERIOD = "10y"

RUSH_THRESHOLD = 75.0
DRIFT_LOWER = 60.0
SCATTER_UPPER = 40.0
FLEE_THRESHOLD = 15.0


@dataclass
class ActionStats:
    """Action Layer 행동 통계."""

    actions: int = 0
    buy_actions: int = 0
    sell_actions: int = 0
    skipped_sells: int = 0
    opportunity_flee: int = 0
    broken_flee: int = 0
    healthy_rush: int = 0
    crowded_rush: int = 0
    regimes: dict[str, int] = field(default_factory=dict)

    def mark(self, regime: str) -> None:
        self.regimes[regime] = self.regimes.get(regime, 0) + 1


@dataclass
class ActionResult:
    """단일 전략 결과."""

    name: str
    portfolio_values: list[float] = field(default_factory=list)
    stats: ActionStats = field(default_factory=ActionStats)

    def final(self) -> float:
        return self.portfolio_values[-1] if self.portfolio_values else INITIAL_CASH

    def return_pct(self) -> float:
        return (self.final() / INITIAL_CASH - 1) * 100

    def mdd(self) -> float:
        peak = INITIAL_CASH
        max_dd = 0.0
        for value in self.portfolio_values:
            peak = max(peak, value)
            dd = (value - peak) / peak * 100
            max_dd = min(max_dd, dd)
        return max_dd


def _close_series(df: pd.DataFrame) -> pd.Series:
    """일봉 DataFrame에서 날짜 인덱스 Close 시계열을 추출한다."""
    data = df.copy()
    if "Date" in data.columns:
        data["Date"] = pd.to_datetime(data["Date"])
        data = data.set_index("Date")
    close = data["Close"].copy()
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]
    close.index = pd.to_datetime(close.index)
    return close.sort_index().dropna()


def _trend_frame(close: pd.Series) -> pd.DataFrame:
    """Action Layer가 사용할 가격 기반 추세 컨텍스트를 만든다."""
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()
    high_52w = close.rolling(252).max()
    low_52w = close.rolling(252).min()
    ma200_slope = ma200.pct_change(63) * 100
    ma200_deviation = (close / ma200 - 1) * 100
    position_52w = (close - low_52w) / (high_52w - low_52w) * 100

    trend_quality = pd.Series(0.0, index=close.index)
    trend_quality += (close > ma200).astype(float) * 25
    trend_quality += (ma50 > ma200).astype(float) * 20
    trend_quality += (ma200_slope > 0).astype(float) * 20
    trend_quality += (ma200_deviation > -20).astype(float) * 15
    trend_quality += (position_52w > 35).astype(float) * 20

    return pd.DataFrame({
        "ma200_deviation": ma200_deviation,
        "position_52w": position_52w,
        "trend_quality": trend_quality.clip(0, 100),
        "return_63d": close.pct_change(63) * 100,
    })


def _action_decision(score: float, ctx: pd.Series, profile: str) -> tuple[str, str, float]:
    """
    점수와 추세 컨텍스트로 regime/action/ratio를 반환한다.
    ratio는 매수 시 현금 비율, 매도 시 보유 주식 비율이다.
    """
    trend = float(ctx.get("trend_quality", 50) or 50)
    ma200_dev = float(ctx.get("ma200_deviation", 0) or 0)

    if profile in {"balanced", "v61"}:
        if score >= RUSH_THRESHOLD:
            if trend >= 75 and ma200_dev < 45:
                return "HEALTHY_RUSH", "SELL", 0.05
            if trend >= 70 and ma200_dev < 65:
                return "HEALTHY_RUSH", "SELL", 0.08
            if trend < 45 or ma200_dev > 90:
                return "CROWDED_RUSH", "SELL", 0.30
            return "NORMAL_RUSH", "SELL", 0.15

        if score >= DRIFT_LOWER:
            if trend >= 75:
                return "HEALTHY_DRIFT", "SELL", 0.02
            return "NORMAL_DRIFT", "SELL", 0.06

        if score <= FLEE_THRESHOLD:
            if trend >= 55 and ma200_dev > -25:
                return "OPPORTUNITY_FLEE", "BUY", 0.22
            if trend < 35 or ma200_dev < -35:
                return "BROKEN_FLEE", "HOLD", 0.0
            return "NORMAL_FLEE", "BUY", 0.08

        if score <= SCATTER_UPPER:
            if trend >= 60 and ma200_dev > -20:
                return "OPPORTUNITY_SCATTER", "BUY", 0.04
            return "NORMAL_SCATTER", "HOLD", 0.0

        return "CALM", "HOLD", 0.0

    if score >= RUSH_THRESHOLD:
        if trend >= 70 and ma200_dev < 65:
            return "HEALTHY_RUSH", "HOLD", 0.0
        if trend < 45 or ma200_dev > 90:
            return "CROWDED_RUSH", "SELL", 0.20
        return "NORMAL_RUSH", "SELL", 0.08

    if score >= DRIFT_LOWER:
        if trend >= 65:
            return "HEALTHY_DRIFT", "HOLD", 0.0
        return "NORMAL_DRIFT", "SELL", 0.03

    if score <= FLEE_THRESHOLD:
        if trend >= 55 and ma200_dev > -25:
            return "OPPORTUNITY_FLEE", "BUY", 0.30
        if trend < 35 or ma200_dev < -35:
            return "BROKEN_FLEE", "BUY", 0.05
        return "NORMAL_FLEE", "BUY", 0.15

    if score <= SCATTER_UPPER:
        if trend >= 60 and ma200_dev > -20:
            return "OPPORTUNITY_SCATTER", "BUY", 0.10
        return "NORMAL_SCATTER", "HOLD", 0.0

    return "CALM", "HOLD", 0.0


def _run_action_layer(close: pd.Series, herd: pd.Series, profile: str) -> ActionResult:
    """Action Layer 동적 비율 전략을 실행한다."""
    result = ActionResult(name=f"ActionLayer-{profile}")
    trend = _trend_frame(close).reindex(close.index).ffill()

    price0 = float(close.iloc[0])
    cash, shares = _buy(INITIAL_CASH, 0.0, price0, ratio=1.0)

    last_sell_pos = -SIGNAL_COOLDOWN - 1
    last_buy_pos = -SIGNAL_COOLDOWN - 1
    previous_score: float | None = None
    previous_action = "HOLD"
    action_days = 0

    for i, (date, price) in enumerate(close.items()):
        price = float(price)
        score = float(herd.get(date, float("nan")))

        if pd.notna(score):
            decision_score = score
            if profile == "v61" and previous_score is not None:
                for boundary in (FLEE_THRESHOLD, SCATTER_UPPER, DRIFT_LOWER, RUSH_THRESHOLD):
                    if abs(score - boundary) <= 2 and (score - boundary) * (previous_score - boundary) < 0:
                        decision_score = boundary - 0.01 if previous_score < boundary else boundary + 0.01
                        break

            regime, action, ratio = _action_decision(decision_score, trend.loc[date], profile)
            if action == previous_action:
                action_days += 1
            else:
                previous_action = action
                action_days = 1

            if profile == "v61" and ratio > 0:
                lifecycle_factor = 0.65 if action_days <= 5 else 1.0 if action_days <= 20 else 0.82 if action_days <= 45 else 0.55
                ratio = round(ratio * lifecycle_factor, 2)

            result.stats.mark(regime)

            sell_ok = (i - last_sell_pos) > SIGNAL_COOLDOWN
            buy_ok = (i - last_buy_pos) > SIGNAL_COOLDOWN

            if regime == "HEALTHY_RUSH":
                result.stats.healthy_rush += 1
                result.stats.skipped_sells += 1
            elif regime == "CROWDED_RUSH":
                result.stats.crowded_rush += 1
            elif regime == "OPPORTUNITY_FLEE":
                result.stats.opportunity_flee += 1
            elif regime == "BROKEN_FLEE":
                result.stats.broken_flee += 1

            if action == "SELL" and ratio > 0 and shares > 0 and sell_ok:
                cash, shares = _sell(cash, shares, price, ratio)
                last_sell_pos = i
                result.stats.actions += 1
                result.stats.sell_actions += 1
            elif action == "BUY" and ratio > 0 and cash > 1.0 and buy_ok:
                cash, shares = _buy(cash, shares, price, ratio)
                last_buy_pos = i
                result.stats.actions += 1
                result.stats.buy_actions += 1

            previous_score = score

        result.portfolio_values.append(cash + shares * price)

    return result


def _return_capture(strategy_return: float, buyhold_return: float) -> float | None:
    if buyhold_return == 0:
        return None
    return strategy_return / buyhold_return * 100


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:+.1f}%"


def _fmt_num(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.1f}"


def _avg(rows: list[dict], key: str) -> float | None:
    values = [row[key] for row in rows if row.get(key) is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _period_years(period: str) -> float:
    """yfinance period 문자열을 대략적인 연 단위로 변환한다."""
    if period.endswith("y"):
        return float(period[:-1])
    return 1.0


def _stored_herd_series(ticker: str, dates: pd.DatetimeIndex) -> pd.Series:
    """백필된 주간 점수만 사용하고 다음 거래일까지 forward-fill한다."""
    with _SessionFactory() as session:
        rows = (session.query(HerdScore)
                .filter(HerdScore.ticker == ticker)
                .order_by(HerdScore.score_date.asc()).all())
    series = pd.Series(
        {pd.Timestamp(row.score_date): float(row.herd_score) for row in rows},
        name="herd_score",
        dtype=float,
    )
    if series.empty:
        raise ValueError("저장된 HERD 백필 데이터 없음")
    return series.reindex(dates.union(series.index)).sort_index().ffill().reindex(dates)


def run_one(ticker: str, *, stored: bool = False) -> dict:
    """단일 티커의 A/B/D 비교 결과를 만든다."""
    df = collect(ticker, period=DATA_PERIOD)
    close = _close_series(df)
    herd = _stored_herd_series(ticker, close.index) if stored else _build_herd_series(df).reindex(close.index).ffill()

    buyhold = _run_strategy_a(close)
    fixed = _run_strategy_b(close, herd)
    growth = _run_action_layer(close, herd, "growth")
    balanced = _run_action_layer(close, herd, "v61")

    buyhold_return = buyhold.return_pct()
    fixed_return = fixed.return_pct()
    growth_return = growth.return_pct()
    balanced_return = balanced.return_pct()
    buyhold_mdd = buyhold.mdd()
    fixed_mdd = fixed.mdd()
    growth_mdd = growth.mdd()
    balanced_mdd = balanced.mdd()

    return {
        "ticker": ticker,
        "start": close.index[0].strftime("%Y-%m-%d"),
        "end": close.index[-1].strftime("%Y-%m-%d"),
        "buyhold_return": buyhold_return,
        "fixed_return": fixed_return,
        "growth_return": growth_return,
        "balanced_return": balanced_return,
        "fixed_capture": _return_capture(fixed_return, buyhold_return),
        "growth_capture": _return_capture(growth_return, buyhold_return),
        "balanced_capture": _return_capture(balanced_return, buyhold_return),
        "growth_delta": growth_return - fixed_return,
        "balanced_delta": balanced_return - fixed_return,
        "buyhold_mdd": buyhold_mdd,
        "fixed_mdd": fixed_mdd,
        "growth_mdd": growth_mdd,
        "balanced_mdd": balanced_mdd,
        "fixed_mdd_improvement": fixed_mdd - buyhold_mdd,
        "growth_mdd_improvement": growth_mdd - buyhold_mdd,
        "balanced_mdd_improvement": balanced_mdd - buyhold_mdd,
        "growth_mdd_delta": growth_mdd - fixed_mdd,
        "balanced_mdd_delta": balanced_mdd - fixed_mdd,
        "growth_actions": growth.stats.actions,
        "growth_buy_actions": growth.stats.buy_actions,
        "growth_sell_actions": growth.stats.sell_actions,
        "balanced_actions": balanced.stats.actions,
        "balanced_buy_actions": balanced.stats.buy_actions,
        "balanced_sell_actions": balanced.stats.sell_actions,
        "balanced_skipped_sells": balanced.stats.skipped_sells,
        "balanced_healthy_rush": balanced.stats.healthy_rush,
        "balanced_crowded_rush": balanced.stats.crowded_rush,
        "balanced_opportunity_flee": balanced.stats.opportunity_flee,
        "balanced_broken_flee": balanced.stats.broken_flee,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="HERD Action Layer walk-forward 후보 검증")
    parser.add_argument("--full", action="store_true", help="전 섹터 50+ 종목 검증")
    parser.add_argument("--tickers", nargs="+", help="검증할 티커 직접 지정")
    args = parser.parse_args()
    tickers = args.tickers or (DIVERSE_TICKERS if args.full else SMOKE_TICKERS)
    print("HERD Action Layer 사전 백테스트")
    print(f"대상: {len(tickers)}종목 | 기간: {DATA_PERIOD} | 유니버스: {UNIVERSE_VERSION}")
    print("D/E 전략은 HERD 점수와 가격 기반 추세 품질로 매수/익절 비율을 동적으로 조정합니다.\n")

    rows: list[dict] = []
    for ticker in tickers:
        try:
            print(f"[{ticker}] 계산 중...", end=" ", flush=True)
            row = run_one(ticker, stored=args.full)
            rows.append(row)
            print(
                f"완료 | B {_fmt_pct(row['fixed_return'])} → "
                f"D {_fmt_pct(row['growth_return'])} / "
                f"v6.1 {_fmt_pct(row['balanced_return'])}"
            )
        except Exception as e:
            print(f"실패: {e}")

    print("\n1) 수익률 / MDD 비교")
    header = (
        "Ticker | BuyHold | Fixed B | Growth D | Balanced E | "
        "D Cap | E Cap | B MDD+ | D MDD+ | E MDD+"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['ticker']:>6} | "
            f"{_fmt_pct(row['buyhold_return']):>8} | "
            f"{_fmt_pct(row['fixed_return']):>7} | "
            f"{_fmt_pct(row['growth_return']):>8} | "
            f"{_fmt_pct(row['balanced_return']):>10} | "
            f"{_fmt_pct(row['growth_capture']):>6} | "
            f"{_fmt_pct(row['balanced_capture']):>6} | "
            f"{_fmt_pct(row['fixed_mdd_improvement']):>7} | "
            f"{_fmt_pct(row['growth_mdd_improvement']):>7} | "
            f"{_fmt_pct(row['balanced_mdd_improvement']):>7}"
        )

    print("\n2) Balanced Action Layer 행동 통계")
    header = "Ticker | v6.1 Actions | Buy | Sell | SkipSell | HealthyRush | CrowdedRush | OppFlee | BrokenFlee"
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['ticker']:>6} | "
            f"{row['balanced_actions']:>7} | "
            f"{row['balanced_buy_actions']:>3} | "
            f"{row['balanced_sell_actions']:>4} | "
            f"{row['balanced_skipped_sells']:>8} | "
            f"{row['balanced_healthy_rush']:>11} | "
            f"{row['balanced_crowded_rush']:>11} | "
            f"{row['balanced_opportunity_flee']:>7} | "
            f"{row['balanced_broken_flee']:>10}"
        )

    print("\n3) 평균 요약")
    print(f"- Buy & Hold 평균 수익률: {_fmt_pct(_avg(rows, 'buyhold_return'))}")
    print(f"- Fixed HERD 평균 수익률: {_fmt_pct(_avg(rows, 'fixed_return'))}")
    print(f"- Growth Action 평균 수익률: {_fmt_pct(_avg(rows, 'growth_return'))}")
    print(f"- HERD v6.1 평균 수익률: {_fmt_pct(_avg(rows, 'balanced_return'))}")
    print(f"- Growth Action 수익률 변화: {_fmt_pct(_avg(rows, 'growth_delta'))}")
    print(f"- HERD v6.1 수익률 변화: {_fmt_pct(_avg(rows, 'balanced_delta'))}")
    print(f"- Fixed 수익률 보존율: {_fmt_pct(_avg(rows, 'fixed_capture'))}")
    print(f"- Growth Action 수익률 보존율: {_fmt_pct(_avg(rows, 'growth_capture'))}")
    print(f"- HERD v6.1 수익률 보존율: {_fmt_pct(_avg(rows, 'balanced_capture'))}")
    print(f"- Fixed MDD 개선: {_fmt_pct(_avg(rows, 'fixed_mdd_improvement'))}")
    print(f"- Growth Action MDD 개선: {_fmt_pct(_avg(rows, 'growth_mdd_improvement'))}")
    print(f"- HERD v6.1 MDD 개선: {_fmt_pct(_avg(rows, 'balanced_mdd_improvement'))}")
    print(f"- Growth Action 평균 거래 수: {_fmt_num(_avg(rows, 'growth_actions'))}")
    print(f"- HERD v6.1 평균 거래 수: {_fmt_num(_avg(rows, 'balanced_actions'))}")
    years = _period_years(DATA_PERIOD)
    balanced_actions = _avg(rows, "balanced_actions")
    annual_actions = balanced_actions / years if balanced_actions is not None else None
    print(f"- HERD v6.1 연평균 거래 수: {_fmt_num(annual_actions)}")

    print("\n판정 기준")
    print("- 채택 후보: Action 수익률 보존율 70% 이상 + MDD 개선 5%p 이상")
    print("- 운영 적합 거래 빈도: 연 4~10회 수준")
    print("- 보류: 수익률 보존율 개선이 작거나 MDD 개선이 기존보다 크게 악화")


if __name__ == "__main__":
    main()
