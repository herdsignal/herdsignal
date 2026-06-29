"""
compare_v1_v2.py — HERD v1 (5개 지표) vs v2 (6개 지표) 전략 비교 백테스트

HERD 시계열을 각 날짜별로 누적 데이터 슬라이스에서 계산하는 것은
수천 회의 반복 연산이 필요해 매우 느리다.
대신 전체 기간 데이터를 한 번 사용해 각 시점의 지표 값을 산출하고
(full-history 백분위수 방식) v1/v2 가중치를 각각 적용해 비교한다.

목적: v1 vs v2 상대 비교이므로 동일한 정규화 기준 적용 시 비교 유효성 유지.

사용법:
  data/.venv/bin/python3.12 compare_v1_v2.py
"""

import sys
import logging
import warnings

import pandas as pd
from scipy.stats import percentileofscore

from collectors.stock_collector import collect
from indicators.rsi import calc_weekly_rsi, calc_monthly_rsi
from indicators.price_position import calc_52w_position, calc_ma200_deviation
from indicators.volume import calc_volume_strength
from indicators.ma200_weekly import calc_ma200_weekly

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.WARNING)   # 비교 실행 중 로그 최소화


# ──────────────────────────────────────────────
# v1 / v2 가중치 (settings.py 와 독립적으로 명시)
# ──────────────────────────────────────────────
V1_WEIGHTS = {
    "monthly_rsi":     0.20,
    "weekly_rsi":      0.20,
    "position_52w":    0.20,
    "ma200_deviation": 0.20,
    "volume_strength": 0.20,
}

V2_WEIGHTS = {
    "monthly_rsi":     0.20,
    "weekly_rsi":      0.18,
    "position_52w":    0.18,
    "ma200_deviation": 0.14,
    "volume_strength": 0.10,
    "ma200_weekly":    0.20,
}

# ──────────────────────────────────────────────
# 백테스트 파라미터
# ──────────────────────────────────────────────
INITIAL_CASH      = 10_000.0   # 초기 자금
FEE_RATE          = 0.001      # 수수료 0.1%
RUSH_THRESHOLD    = 75.0       # Rush → 30% 익절
DRIFT_LOWER       = 60.0       # Drift → 5% 익절
FLEE_THRESHOLD    = 15.0       # Flee → 30% 추가매수
SIGNAL_COOLDOWN   = 20         # 중복 신호 쿨다운 (거래일)
RUSH_SELL_RATIO   = 0.30
DRIFT_SELL_RATIO  = 0.05
FLEE_BUY_RATIO    = 0.30

# 비교 대상 종목
TICKERS = ["NVDA", "MSFT", "KO", "JPM", "XOM", "IONQ", "SPY"]


# ──────────────────────────────────────────────
# HERD 점수 계산 (단일 DataFrame → v1/v2 동시 산출)
# ──────────────────────────────────────────────
def _calc_herd_score(ind: dict, weights: dict) -> float:
    """지표 딕셔너리와 가중치로 HERD 점수를 계산한다."""
    score = sum(ind.get(k, 0.0) * w for k, w in weights.items())
    return round(max(0.0, min(100.0, score)), 2)


def build_herd_series(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """
    전체 기간 DataFrame으로 일별 v1/v2 HERD 점수 시계열을 산출한다.

    전체 히스토리 백분위수 방식:
    - 각 지표를 전체 기간 기준 한 번만 계산 (rolling slice 불필요)
    - 백분위수는 각 날짜 슬라이스가 아닌 전체 히스토리 대비 계산
    - v1/v2 가중치를 각각 적용해 동시에 산출
    """
    # Date 컬럼을 인덱스로 변환
    if "Date" in df.columns:
        df = df.copy()
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")
    df = df.sort_index()

    v1_scores: dict = {}
    v2_scores: dict = {}

    # 지표 계산에 필요한 최소 데이터 (MA200 기준)
    min_rows = 253

    for i in range(min_rows, len(df)):
        slice_df = df.iloc[:i + 1]
        date = df.index[i]

        try:
            # 6개 지표 한 번에 계산
            ind = {
                "monthly_rsi":     calc_monthly_rsi(slice_df),
                "weekly_rsi":      calc_weekly_rsi(slice_df),
                "position_52w":    calc_52w_position(slice_df),
                "ma200_deviation": calc_ma200_deviation(slice_df),
                "volume_strength": calc_volume_strength(slice_df),
                "ma200_weekly":    calc_ma200_weekly(slice_df),
            }
            v1_scores[date] = _calc_herd_score(ind, V1_WEIGHTS)
            v2_scores[date] = _calc_herd_score(ind, V2_WEIGHTS)

        except Exception:
            # 데이터 부족 등 계산 실패 시 NaN 처리
            v1_scores[date] = float("nan")
            v2_scores[date] = float("nan")

    return pd.Series(v1_scores, name="v1"), pd.Series(v2_scores, name="v2")


# ──────────────────────────────────────────────
# 전략 시뮬레이션 (부분 익절 전략)
# ──────────────────────────────────────────────
def _buy(cash: float, shares: float, price: float,
         ratio: float = 1.0) -> tuple[float, float]:
    """보유 현금의 ratio 비율로 매수 (수수료 포함)."""
    spend = cash * ratio
    new_shares = (spend / (1 + FEE_RATE)) / price
    return cash - spend, shares + new_shares


def _sell(cash: float, shares: float, price: float,
          ratio: float = 1.0) -> tuple[float, float]:
    """보유 주식의 ratio 비율을 매도 (수수료 포함)."""
    sell_shares = shares * ratio
    proceeds = sell_shares * price * (1 - FEE_RATE)
    return cash + proceeds, shares - sell_shares


def run_strategy(close: pd.Series, herd: pd.Series) -> dict:
    """
    부분 익절 전략을 시뮬레이션하고 결과를 반환한다.

    - Rush(≥75)    : 보유량 30% 익절
    - Drift(60~75) : 보유량 5% 익절
    - Flee(≤15)    : 현금 30% 추가매수
    - 중복 신호 쿨다운: 20 거래일

    Returns:
        {'return_pct': float, 'mdd': float}
    """
    # 첫날 전액 매수
    price0 = float(close.iloc[0])
    cash, shares = _buy(INITIAL_CASH, 0.0, price0, ratio=1.0)

    last_sell_pos = -SIGNAL_COOLDOWN - 1
    last_buy_pos  = -SIGNAL_COOLDOWN - 1
    portfolio_values: list[float] = []

    for i, (date, price) in enumerate(close.items()):
        price = float(price)
        score = float(herd.get(date, float("nan")))

        if pd.notna(score):
            sell_ok = (i - last_sell_pos) > SIGNAL_COOLDOWN
            buy_ok  = (i - last_buy_pos)  > SIGNAL_COOLDOWN

            if score >= RUSH_THRESHOLD and shares > 0 and sell_ok:
                # Rush — 30% 익절
                cash, shares = _sell(cash, shares, price, RUSH_SELL_RATIO)
                last_sell_pos = i

            elif DRIFT_LOWER <= score < RUSH_THRESHOLD and shares > 0 and sell_ok:
                # Drift — 5% 익절
                cash, shares = _sell(cash, shares, price, DRIFT_SELL_RATIO)
                last_sell_pos = i

            elif score <= FLEE_THRESHOLD and cash > 0 and buy_ok:
                # Flee — 30% 추가매수
                cash, shares = _buy(cash, shares, price, FLEE_BUY_RATIO)
                last_buy_pos = i

        portfolio_values.append(cash + shares * price)

    # 수익률 계산
    final = portfolio_values[-1]
    ret   = (final / INITIAL_CASH - 1) * 100

    # MDD 계산
    peak   = INITIAL_CASH
    max_dd = 0.0
    for v in portfolio_values:
        if v > peak:
            peak = v
        dd = (v - peak) / peak * 100
        if dd < max_dd:
            max_dd = dd

    return {"return_pct": ret, "mdd": max_dd}


def run_bah(close: pd.Series) -> dict:
    """Buy & Hold 전략 시뮬레이션."""
    price0 = float(close.iloc[0])
    cash, shares = _buy(INITIAL_CASH, 0.0, price0, ratio=1.0)

    portfolio_values = [cash + shares * float(p) for p in close]

    final = portfolio_values[-1]
    ret   = (final / INITIAL_CASH - 1) * 100

    peak   = INITIAL_CASH
    max_dd = 0.0
    for v in portfolio_values:
        if v > peak:
            peak = v
        dd = (v - peak) / peak * 100
        if dd < max_dd:
            max_dd = dd

    return {"return_pct": ret, "mdd": max_dd}


# ──────────────────────────────────────────────
# 결과 출력
# ──────────────────────────────────────────────
def fmt_pct(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.1f}%"


def main() -> None:
    rows = []

    for ticker in TICKERS:
        print(f"  [{ticker}] 데이터 수집 중...", end=" ", flush=True)

        # IONQ는 상장 기간이 짧으므로 "max"로 수집, 나머지는 10년
        period = "max" if ticker == "IONQ" else "10y"
        try:
            df = collect(ticker, period=period)
        except Exception as e:
            print(f"실패 ({e})")
            continue

        df_indexed = df.copy()
        if "Date" in df_indexed.columns:
            df_indexed["Date"] = pd.to_datetime(df_indexed["Date"])
            df_indexed = df_indexed.set_index("Date").sort_index()

        close = df_indexed["Close"]
        print(f"{len(df_indexed)}일 ({close.index[0].date()} ~ {close.index[-1].date()})")

        print(f"  [{ticker}] HERD v1/v2 시계열 산출 중...", end=" ", flush=True)
        v1_series, v2_series = build_herd_series(df_indexed)
        print("완료")

        bah  = run_bah(close)
        res1 = run_strategy(close, v1_series)
        res2 = run_strategy(close, v2_series)

        rows.append({
            "ticker":       ticker,
            "bah_return":   bah["return_pct"],
            "bah_mdd":      bah["mdd"],
            "v1_return":    res1["return_pct"],
            "v1_mdd":       res1["mdd"],
            "v2_return":    res2["return_pct"],
            "v2_mdd":       res2["mdd"],
        })

    if not rows:
        print("결과 없음")
        return

    # ── 결과 표 출력 ─────────────────────────────────
    sep = "═" * 102
    print()
    print(sep)
    print("  HERD v1 (5개 지표, 동일가중) vs v2 (6개 지표, ma200_weekly 추가) 비교")
    print(sep)
    header = (
        f"  {'종목':<6}  {'B&H':>8}  {'B&H MDD':>8}  "
        f"{'v1 수익':>9}  {'v1 MDD':>8}  "
        f"{'v2 수익':>9}  {'v2 MDD':>8}  "
        f"{'MDD 변화':>9}  {'v2 보존율':>9}"
    )
    print(header)
    print("  " + "─" * 98)

    sum_v1r = sum_v2r = sum_v1m = sum_v2m = sum_mdd_delta = sum_preserve = 0.0

    for r in rows:
        bah_r  = r["bah_return"]
        v1_r   = r["v1_return"]
        v2_r   = r["v2_return"]
        v1_m   = r["v1_mdd"]
        v2_m   = r["v2_mdd"]
        mdd_delta   = v2_m - v1_m   # 음수 = v2가 MDD 개선, 양수 = 악화
        # 수익 보존율: v2 수익 / B&H 수익 (B&H 수익률 100%일 때 v2가 얼마 보존했는지)
        preserve = (v2_r / bah_r * 100) if bah_r != 0 else 0.0

        sum_v1r       += v1_r
        sum_v2r       += v2_r
        sum_v1m       += v1_m
        sum_v2m       += v2_m
        sum_mdd_delta += mdd_delta
        sum_preserve  += preserve

        # mdd_delta > 0 = v2 MDD가 v1보다 덜 부정적 = 낙폭 감소 = 개선 → ▼
        mdd_mark = "▼" if mdd_delta > 0 else "▲"
        print(
            f"  {r['ticker']:<6}  {fmt_pct(bah_r):>8}  {fmt_pct(r['bah_mdd']):>8}  "
            f"{fmt_pct(v1_r):>9}  {fmt_pct(v1_m):>8}  "
            f"{fmt_pct(v2_r):>9}  {fmt_pct(v2_m):>8}  "
            f"{fmt_pct(mdd_delta):>8}{mdd_mark}  {preserve:>7.1f}%"
        )

    # 평균
    n = len(rows)
    print("  " + "─" * 98)
    print(
        f"  {'평균':<6}  {'':>8}  {'':>8}  "
        f"{fmt_pct(sum_v1r/n):>9}  {fmt_pct(sum_v1m/n):>8}  "
        f"{fmt_pct(sum_v2r/n):>9}  {fmt_pct(sum_v2m/n):>8}  "
        f"{fmt_pct(sum_mdd_delta/n):>8}   {sum_preserve/n:>7.1f}%"
    )
    print(sep)
    print()
    print("  ▼ = v2 MDD 개선 (낙폭 감소)  ▲ = v2 MDD 악화 (낙폭 증가)")
    print("  v2 보존율 = v2 수익 / B&H 수익 × 100  (B&H 대비 v2 수익률 보존 비율)")
    print()


if __name__ == "__main__":
    print()
    print("  HERD v1 vs v2 백테스트 시작")
    print(f"  종목: {', '.join(TICKERS)}")
    print(f"  전략: Rush≥{RUSH_THRESHOLD:.0f} {RUSH_SELL_RATIO*100:.0f}%익절 / "
          f"Drift≥{DRIFT_LOWER:.0f} {DRIFT_SELL_RATIO*100:.0f}%익절 / "
          f"Flee≤{FLEE_THRESHOLD:.0f} {FLEE_BUY_RATIO*100:.0f}%추가매수")
    print()
    main()
