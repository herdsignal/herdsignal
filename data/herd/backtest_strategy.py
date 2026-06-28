"""
herd/backtest_strategy.py — HERD Index 전략 비교 백테스트
Buy & Hold / HERD 단순 신호 / HERD 부분 익절 3가지 전략을 동일 기간에 비교한다.
"""

import logging
from dataclasses import dataclass, field

import pandas as pd

from collectors.stock_collector import collect
from config.settings import HERD_THRESHOLDS
from herd.backtest import _build_herd_series

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 전략 공통 설정
# ──────────────────────────────────────────────
INITIAL_CASH     = 10_000.0   # 초기 자금 (달러)
FEE_RATE         = 0.001      # 매수/매도 수수료 각 0.1%

# 전략 C 부분 익절/매수 비율 (그리드 서치 최적값)
RUSH_SELL_RATIO     = 0.30   # Rush → 보유 주식의 30% 매도
DRIFT_SELL_RATIO    = 0.05   # Drift → 보유 주식의 5% 매도
FLEE_BUY_RATIO      = 0.10   # Flee → 보유 현금의 10%로 매수
SCATTER_BUY_RATIO   = 0.15   # Scatter → 보유 현금의 15%로 매수

# 전략 B/C HERD 임계값 (settings.py에서 관리)
RUSH_THRESHOLD    = HERD_THRESHOLDS["rush"]   # 75.0 (백분위수 정규화 기준 최적값)
FLEE_THRESHOLD    = HERD_THRESHOLDS["flee"]   # 15.0
DRIFT_LOWER       = 60.0                       # Drift: 60~75
SCATTER_UPPER     = 40.0                       # Scatter: 15~40

# 전략 C 중복 신호 쿨다운 (거래일)
SIGNAL_COOLDOWN_C = 20


# ──────────────────────────────────────────────
# 결과 자료구조
# ──────────────────────────────────────────────
@dataclass
class StrategyResult:
    name:           str
    portfolio_values: list[float] = field(default_factory=list)  # 일별 총자산
    trade_count:    int = 0
    cash_ratios:    list[float] = field(default_factory=list)    # 일별 현금 비율

    def final_value(self) -> float:
        return self.portfolio_values[-1] if self.portfolio_values else INITIAL_CASH

    def total_return_pct(self) -> float:
        return (self.final_value() / INITIAL_CASH - 1) * 100

    def mdd(self) -> float:
        """MDD(최대 낙폭): 고점 대비 최대 하락률 (%)."""
        peak = INITIAL_CASH
        max_dd = 0.0
        for v in self.portfolio_values:
            if v > peak:
                peak = v
            dd = (v - peak) / peak * 100
            if dd < max_dd:
                max_dd = dd
        return max_dd

    def avg_cash_ratio(self) -> float:
        if not self.cash_ratios:
            return 0.0
        return sum(self.cash_ratios) / len(self.cash_ratios) * 100


# ──────────────────────────────────────────────
# 매매 헬퍼
# ──────────────────────────────────────────────
def _buy(cash: float, shares: float, price: float,
         ratio: float = 1.0) -> tuple[float, float]:
    """
    보유 현금의 ratio 비율로 주식을 매수한다.
    수수료 포함. 잔여 현금과 추가된 주식 수를 반환한다.
    """
    spend = cash * ratio
    actual_spend = spend / (1 + FEE_RATE)   # 수수료 제외 실매수금
    new_shares = actual_spend / price
    return cash - spend, shares + new_shares


def _sell(cash: float, shares: float, price: float,
          ratio: float = 1.0) -> tuple[float, float]:
    """
    보유 주식의 ratio 비율을 매도한다.
    수수료 포함. 잔여 현금과 남은 주식 수를 반환한다.
    """
    sell_shares = shares * ratio
    proceeds = sell_shares * price * (1 - FEE_RATE)
    return cash + proceeds, shares - sell_shares


# ──────────────────────────────────────────────
# 전략 A — Buy & Hold
# ──────────────────────────────────────────────
def _run_strategy_a(close: pd.Series) -> StrategyResult:
    """시작일 전액 매수 후 만기까지 보유."""
    result = StrategyResult(name="A — Buy & Hold")

    # 첫날 전액 매수 (수수료 포함)
    price0 = float(close.iloc[0])
    cash, shares = _buy(INITIAL_CASH, 0.0, price0, ratio=1.0)

    for price in close:
        total = cash + shares * float(price)
        result.portfolio_values.append(total)
        result.cash_ratios.append(cash / total if total > 0 else 0)

    return result


# ──────────────────────────────────────────────
# 전략 B — HERD 단순 신호
# ──────────────────────────────────────────────
def _run_strategy_b(close: pd.Series,
                    herd: pd.Series) -> StrategyResult:
    """
    Rush(≥80) → 전량 매도 / Flee(≤20) → 전량 매수.
    신호 없으면 포지션 유지.
    """
    result = StrategyResult(name="B — HERD 단순 신호")

    # 첫날 전액 매수로 시작
    price0 = float(close.iloc[0])
    cash, shares = _buy(INITIAL_CASH, 0.0, price0, ratio=1.0)

    for date, price in close.items():
        price = float(price)
        score = float(herd.get(date, float("nan")))

        if pd.notna(score):
            if score >= RUSH_THRESHOLD and shares > 0:
                # Rush → 전량 매도
                cash, shares = _sell(cash, shares, price, ratio=1.0)
                result.trade_count += 1
            elif score <= FLEE_THRESHOLD and cash > 0:
                # Flee → 전액 매수
                cash, shares = _buy(cash, shares, price, ratio=1.0)
                result.trade_count += 1

        total = cash + shares * price
        result.portfolio_values.append(total)
        result.cash_ratios.append(cash / total if total > 0 else 0)

    return result


# ──────────────────────────────────────────────
# 전략 C — HERD 부분 익절 (핵심 전략)
# ──────────────────────────────────────────────
def _run_strategy_c(close: pd.Series,
                    herd: pd.Series) -> StrategyResult:
    """
    단계별 부분 익절/매수 전략.
    중복 신호는 쿨다운(20 거래일) 이내 재발생을 무시한다.
    """
    result = StrategyResult(name="C — HERD 부분 익절")

    # 첫날 전액 매수로 시작
    price0 = float(close.iloc[0])
    cash, shares = _buy(INITIAL_CASH, 0.0, price0, ratio=1.0)

    # 방향별 마지막 신호 위치 추적 (쿨다운 관리)
    # "sell" = Rush/Drift 계열, "buy" = Flee/Scatter 계열
    last_signal_pos: dict[str, int] = {"sell": -SIGNAL_COOLDOWN_C - 1,
                                       "buy":  -SIGNAL_COOLDOWN_C - 1}
    dates = close.index.tolist()

    for i, (date, price) in enumerate(close.items()):
        price = float(price)
        score = float(herd.get(date, float("nan")))

        if pd.notna(score):
            sell_cooldown_ok = (i - last_signal_pos["sell"]) > SIGNAL_COOLDOWN_C
            buy_cooldown_ok  = (i - last_signal_pos["buy"])  > SIGNAL_COOLDOWN_C

            if score >= RUSH_THRESHOLD and shares > 0 and sell_cooldown_ok:
                # Rush → 보유량 30% 매도
                cash, shares = _sell(cash, shares, price, RUSH_SELL_RATIO)
                result.trade_count += 1
                last_signal_pos["sell"] = i

            elif DRIFT_LOWER <= score < RUSH_THRESHOLD and shares > 0 and sell_cooldown_ok:
                # Drift → 보유량 10% 매도
                cash, shares = _sell(cash, shares, price, DRIFT_SELL_RATIO)
                result.trade_count += 1
                last_signal_pos["sell"] = i

            elif score <= FLEE_THRESHOLD and cash > 0 and buy_cooldown_ok:
                # Flee → 현금 30% 매수
                cash, shares = _buy(cash, shares, price, FLEE_BUY_RATIO)
                result.trade_count += 1
                last_signal_pos["buy"] = i

            elif FLEE_THRESHOLD < score <= SCATTER_UPPER and cash > 0 and buy_cooldown_ok:
                # Scatter → 현금 10% 매수
                cash, shares = _buy(cash, shares, price, SCATTER_BUY_RATIO)
                result.trade_count += 1
                last_signal_pos["buy"] = i

        total = cash + shares * price
        result.portfolio_values.append(total)
        result.cash_ratios.append(cash / total if total > 0 else 0)

    return result


# ──────────────────────────────────────────────
# 종목 단위 전략 비교 실행
# ──────────────────────────────────────────────
def run_strategy_backtest(ticker: str) -> tuple[StrategyResult,
                                                StrategyResult,
                                                StrategyResult,
                                                str, str]:
    """
    단일 종목에 대해 3가지 전략을 실행하고 결과를 반환한다.

    Returns:
        (strategy_a, strategy_b, strategy_c, start_date, end_date)
    """
    logger.info(f"[{ticker}] 전략 백테스트 시작")

    # 데이터 수집
    df = collect(ticker)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()
    close = df["Close"]

    # HERD Index 시계열 산출
    logger.info(f"[{ticker}] HERD 시계열 산출 중... ({len(df)}일)")
    herd_series = _build_herd_series(df)

    # HERD 시계열이 시작되는 날부터 전략 기간 맞춤
    # (그 이전 구간은 NaN이므로 전략 B/C는 신호 없이 초기 포지션 유지)
    start_date = close.index[0]
    end_date   = close.index[-1]

    result_a = _run_strategy_a(close)
    result_b = _run_strategy_b(close, herd_series)
    result_c = _run_strategy_c(close, herd_series)

    logger.info(
        f"[{ticker}] 완료 — "
        f"A: {result_a.total_return_pct():+.1f}% | "
        f"B: {result_b.total_return_pct():+.1f}% | "
        f"C: {result_c.total_return_pct():+.1f}%"
    )

    return (result_a, result_b, result_c,
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"))


# ──────────────────────────────────────────────
# 결과 출력
# ──────────────────────────────────────────────
def print_strategy_result(ticker: str,
                          a: StrategyResult,
                          b: StrategyResult,
                          c: StrategyResult,
                          start: str, end: str) -> None:
    """3가지 전략 결과를 지정 형식으로 출력한다."""

    def fmt_money(v: float) -> str:
        return f"${v:,.0f}"

    def fmt_pct(v: float) -> str:
        sign = "+" if v >= 0 else ""
        return f"{sign}{v:.1f}%"

    sep = "=" * 48

    print()
    print(sep)
    print(f"  {ticker} 전략 비교")
    print(f"  기간: {start} ~ {end}")
    print(sep)

    # 전략 A
    print()
    print("  전략 A (Buy & Hold)")
    print(f"    최종 자산  : {fmt_money(a.final_value())}")
    print(f"    총 수익률  : {fmt_pct(a.total_return_pct())}")
    print(f"    MDD        : {fmt_pct(a.mdd())}")

    # 전략 B
    print()
    print("  전략 B (HERD 단순 신호)")
    print(f"    최종 자산  : {fmt_money(b.final_value())}")
    print(f"    총 수익률  : {fmt_pct(b.total_return_pct())}")
    print(f"    MDD        : {fmt_pct(b.mdd())}")
    print(f"    매매 횟수  : {b.trade_count}회")

    # 전략 C
    # MDD는 음수 → C - A 가 양수면 C의 낙폭이 더 작음 = 개선
    mdd_diff = c.mdd() - a.mdd()
    print()
    print("  전략 C (HERD 부분 익절) ← 우리 서비스 전략")
    print(f"    최종 자산  : {fmt_money(c.final_value())}")
    print(f"    총 수익률  : {fmt_pct(c.total_return_pct())}")
    print(f"    MDD        : {fmt_pct(c.mdd())}")
    print(f"    매매 횟수  : {c.trade_count}회")
    print(f"    평균 현금 보유 비율: {c.avg_cash_ratio():.1f}%")

    # 핵심 지표
    print()
    print("  ─── 핵심 지표 ───────────────────────────────")
    direction = "개선 ▼" if mdd_diff > 0 else "악화 ▲"
    print(f"    전략 C vs Buy & Hold MDD 차이: "
          f"{fmt_pct(mdd_diff)} ({direction})")
    ret_diff = c.total_return_pct() - a.total_return_pct()
    print(f"    전략 C vs Buy & Hold 수익률 차이: {fmt_pct(ret_diff)}")
    print()
