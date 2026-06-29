"""
diagnose_xom.py — XOM 백테스트 이상 원인 진단

Buy&Hold +137% vs 전략 C -5.9%의 원인을 분석한다.
신호 발생 내역, 매매 시점별 손익, 현금 보유 패턴을 추적한다.
"""

import warnings
import logging

import pandas as pd

from collectors.stock_collector import collect
from indicators.rsi import calc_weekly_rsi, calc_monthly_rsi
from indicators.price_position import calc_52w_position, calc_ma200_deviation
from indicators.volume import calc_volume_strength
from indicators.ma200_weekly import calc_ma200_weekly

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.WARNING)

# ──────────────────────────────────────────────
# 파라미터 (compare_v1_v2.py와 동일)
# ──────────────────────────────────────────────
INITIAL_CASH    = 10_000.0
FEE_RATE        = 0.001
RUSH_THRESHOLD  = 75.0
DRIFT_LOWER     = 60.0
FLEE_THRESHOLD  = 15.0
SIGNAL_COOLDOWN = 20
RUSH_SELL_RATIO = 0.30
DRIFT_SELL_RATIO= 0.05
FLEE_BUY_RATIO  = 0.30

V1_WEIGHTS = {
    "monthly_rsi":     0.20,
    "weekly_rsi":      0.20,
    "position_52w":    0.20,
    "ma200_deviation": 0.20,
    "volume_strength": 0.20,
}


def build_herd_series_v1(df: pd.DataFrame) -> pd.Series:
    """v1 가중치로 HERD 시계열을 산출한다 (rolling slice 방식)."""
    if "Date" in df.columns:
        df = df.copy()
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")
    df = df.sort_index()

    scores = {}
    min_rows = 253

    for i in range(min_rows, len(df)):
        s = df.iloc[:i + 1]
        date = df.index[i]
        try:
            ind = {
                "monthly_rsi":     calc_monthly_rsi(s),
                "weekly_rsi":      calc_weekly_rsi(s),
                "position_52w":    calc_52w_position(s),
                "ma200_deviation": calc_ma200_deviation(s),
                "volume_strength": calc_volume_strength(s),
            }
            score = sum(ind[k] * w for k, w in V1_WEIGHTS.items())
            scores[date] = round(max(0.0, min(100.0, score)), 2)
        except Exception:
            scores[date] = float("nan")

    return pd.Series(scores, name="herd_v1")


def run_strategy_verbose(close: pd.Series,
                         herd: pd.Series) -> list[dict]:
    """
    전략 C를 실행하며 모든 매매 이벤트를 기록한다.

    Returns:
        매매 로그 리스트 (날짜, 종류, 가격, HERD 점수, 매매 후 현금/주식/총자산)
    """
    price0 = float(close.iloc[0])
    cash = INITIAL_CASH * (1 - FEE_RATE)   # 첫날 전액 매수
    shares = (INITIAL_CASH - cash) / price0 + (INITIAL_CASH / price0)
    # 정확하게 _buy 로직 재현
    spend = INITIAL_CASH
    actual = spend / (1 + FEE_RATE)
    shares = actual / price0
    cash = INITIAL_CASH - spend

    last_sell_pos = -SIGNAL_COOLDOWN - 1
    last_buy_pos  = -SIGNAL_COOLDOWN - 1
    trade_log: list[dict] = []
    daily_log: list[dict] = []

    for i, (date, price) in enumerate(close.items()):
        price = float(price)
        score = float(herd.get(date, float("nan")))
        action = None

        if pd.notna(score):
            sell_ok = (i - last_sell_pos) > SIGNAL_COOLDOWN
            buy_ok  = (i - last_buy_pos)  > SIGNAL_COOLDOWN

            if score >= RUSH_THRESHOLD and shares > 0 and sell_ok:
                # Rush — 30% 익절
                sell_shares = shares * RUSH_SELL_RATIO
                proceeds = sell_shares * price * (1 - FEE_RATE)
                cash += proceeds
                shares -= sell_shares
                last_sell_pos = i
                action = "RUSH_SELL"

            elif DRIFT_LOWER <= score < RUSH_THRESHOLD and shares > 0 and sell_ok:
                # Drift — 5% 익절
                sell_shares = shares * DRIFT_SELL_RATIO
                proceeds = sell_shares * price * (1 - FEE_RATE)
                cash += proceeds
                shares -= sell_shares
                last_sell_pos = i
                action = "DRIFT_SELL"

            elif score <= FLEE_THRESHOLD and cash > 1.0 and buy_ok:
                # Flee — 30% 추가매수
                spend = cash * FLEE_BUY_RATIO
                new_shares = (spend / (1 + FEE_RATE)) / price
                cash -= spend
                shares += new_shares
                last_buy_pos = i
                action = "FLEE_BUY"

        total = cash + shares * price
        daily = {
            "date":   date,
            "price":  price,
            "score":  score,
            "cash":   cash,
            "shares": shares,
            "total":  total,
            "action": action,
        }
        daily_log.append(daily)
        if action:
            trade_log.append(daily)

    return trade_log, daily_log


def analyse_signal_outcome(trade_log: list[dict],
                           close: pd.Series) -> None:
    """신호 발생 후 1/3/6/12개월 주가 흐름을 출력한다."""
    print()
    print("  ── 신호별 이후 주가 흐름 ──────────────────────────────────────────")
    print(f"  {'날짜':<12} {'HERD':>6} {'신호':<12} {'매매가':>8} "
          f"{'1M':>7} {'3M':>7} {'6M':>7} {'12M':>8}")
    print("  " + "─" * 74)

    dates = close.index.tolist()
    for t in trade_log:
        date   = t["date"]
        price  = t["price"]
        score  = t["score"]
        action = t["action"]

        try:
            base_pos = dates.index(date)
        except ValueError:
            continue

        def fwd(days: int) -> str:
            pos = base_pos + days
            if pos >= len(dates):
                return "  N/A"
            fp = float(close.iloc[pos])
            chg = (fp - price) / price * 100
            return f"{chg:+.1f}%"

        action_label = {
            "RUSH_SELL":  "Rush익절(30%)",
            "DRIFT_SELL": "Drift익절(5%)",
            "FLEE_BUY":   "Flee매수(30%)",
        }.get(action, action)

        print(f"  {str(date.date()):<12} {score:>6.1f} {action_label:<12} "
              f"{price:>8.2f} "
              f"{fwd(21):>7} {fwd(63):>7} {fwd(126):>7} {fwd(252):>8}")


def print_cash_flow(daily_log: list[dict], close: pd.Series) -> None:
    """연도별 평균 현금 보유 비율과 기회비용을 출력한다."""
    print()
    print("  ── 연도별 현금 보유 비율 (기회비용 분석) ─────────────────────────")
    print(f"  {'연도':<6} {'평균 현금비율':>13} {'평균 주식비율':>13} {'연간 주가변화':>13}")
    print("  " + "─" * 50)

    df_daily = pd.DataFrame(daily_log).set_index("date")
    df_daily["cash_ratio"] = df_daily["cash"] / df_daily["total"]

    for year in sorted(df_daily.index.year.unique()):
        yr_data = df_daily[df_daily.index.year == year]
        avg_cash = yr_data["cash_ratio"].mean() * 100

        yr_close = close[close.index.year == year]
        if len(yr_close) >= 2:
            yr_chg = (float(yr_close.iloc[-1]) / float(yr_close.iloc[0]) - 1) * 100
            yr_chg_str = f"{yr_chg:+.1f}%"
        else:
            yr_chg_str = "  N/A"

        print(f"  {year:<6} {avg_cash:>12.1f}%  {100-avg_cash:>12.1f}%  {yr_chg_str:>13}")


def main() -> None:
    print()
    print("═" * 72)
    print("  XOM 백테스트 이상 원인 진단")
    print("═" * 72)

    # 1. 데이터 수집
    print("\n  [1/3] 10년 데이터 수집 중...")
    df = collect("XOM", period="10y")
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()
    close = df["Close"]

    start = close.index[0].date()
    end   = close.index[-1].date()
    bah   = (float(close.iloc[-1]) / float(close.iloc[0]) - 1) * 100
    print(f"  기간: {start} ~ {end} ({len(df)}일)")
    print(f"  Buy & Hold 수익률: {bah:+.1f}%")
    print(f"  시작가: ${float(close.iloc[0]):.2f} → 종가: ${float(close.iloc[-1]):.2f}")

    # 2. HERD 시계열 산출
    print("\n  [2/3] HERD v1 시계열 산출 중 (약 2분 소요)...")
    herd = build_herd_series_v1(df)
    valid = herd.dropna()
    print(f"  HERD 산출 기간: {valid.index[0].date()} ~ {valid.index[-1].date()}")
    print(f"  HERD 범위: {valid.min():.1f} ~ {valid.max():.1f} (평균 {valid.mean():.1f})")

    # 3. 신호 통계
    rush_days  = valid[valid >= RUSH_THRESHOLD]
    flee_days  = valid[valid <= FLEE_THRESHOLD]
    drift_days = valid[(valid >= DRIFT_LOWER) & (valid < RUSH_THRESHOLD)]
    print()
    print("  ── 구간별 HERD 분포 ───────────────────────────────────────────────")
    total = len(valid)
    print(f"  Rush (≥{RUSH_THRESHOLD:.0f})  : {len(rush_days):>4}일 ({len(rush_days)/total*100:.1f}%)")
    print(f"  Drift ({DRIFT_LOWER:.0f}~{RUSH_THRESHOLD:.0f}): {len(drift_days):>4}일 ({len(drift_days)/total*100:.1f}%)")
    print(f"  Flee (≤{FLEE_THRESHOLD:.0f})  : {len(flee_days):>4}일 ({len(flee_days)/total*100:.1f}%)")

    # 4. 전략 실행 (상세 로그)
    print("\n  [3/3] 전략 C 시뮬레이션 중...")
    trade_log, daily_log = run_strategy_verbose(close, herd)

    final_total = daily_log[-1]["total"]
    strat_return = (final_total / INITIAL_CASH - 1) * 100
    rush_trades  = [t for t in trade_log if t["action"] == "RUSH_SELL"]
    drift_trades = [t for t in trade_log if t["action"] == "DRIFT_SELL"]
    flee_trades  = [t for t in trade_log if t["action"] == "FLEE_BUY"]

    print()
    print("  ── 전략 실행 요약 ─────────────────────────────────────────────────")
    print(f"  전략 C 최종 수익률 : {strat_return:+.1f}%")
    print(f"  전략 총 매매 횟수  : {len(trade_log)}회")
    print(f"    Rush 익절        : {len(rush_trades)}회")
    print(f"    Drift 익절       : {len(drift_trades)}회")
    print(f"    Flee 매수        : {len(flee_trades)}회")
    print(f"  최종 현금 잔고     : ${daily_log[-1]['cash']:.2f}")
    print(f"  최종 주식 가치     : ${daily_log[-1]['shares'] * float(close.iloc[-1]):.2f}")

    # 5. 신호별 이후 주가
    analyse_signal_outcome(trade_log, close)

    # 6. 현금 보유 패턴
    print_cash_flow(daily_log, close)

    # 7. 진단 요약
    avg_cash = sum(d["cash"] / d["total"] for d in daily_log) / len(daily_log) * 100
    rush_correct = 0
    for t in rush_trades:
        pos = close.index.tolist().index(t["date"])
        future_pos = pos + 126  # 6개월 후
        if future_pos < len(close):
            future_price = float(close.iloc[future_pos])
            if future_price < t["price"]:  # 6개월 후 하락 = 신호 맞음
                rush_correct += 1

    flee_correct = 0
    for t in flee_trades:
        pos = close.index.tolist().index(t["date"])
        future_pos = pos + 126  # 6개월 후
        if future_pos < len(close):
            future_price = float(close.iloc[future_pos])
            if future_price > t["price"]:  # 6개월 후 상승 = 신호 맞음
                flee_correct += 1

    print()
    print("═" * 72)
    print("  진단 결론")
    print("═" * 72)
    print(f"  평균 현금 보유 비율  : {avg_cash:.1f}%")
    if len(rush_trades) > 0:
        print(f"  Rush 신호 6M 정확도 : {rush_correct}/{len(rush_trades)} "
              f"({rush_correct/len(rush_trades)*100:.0f}%)  "
              f"(이후 6개월 하락한 비율)")
    if len(flee_trades) > 0:
        print(f"  Flee 신호 6M 정확도 : {flee_correct}/{len(flee_trades)} "
              f"({flee_correct/len(flee_trades)*100:.0f}%)  "
              f"(이후 6개월 상승한 비율)")
    print()

    if avg_cash > 20:
        print("  ⚠️  현금 과다 보유: Rush 익절 이후 현금을 Flee까지 기다리는 사이")
        print("     주가가 지속 상승해 기회비용이 발생했을 가능성 높음.")
    if len(rush_trades) > 0 and rush_correct / len(rush_trades) < 0.5:
        print("  ⚠️  Rush 신호 오발: 익절 후 주가가 오히려 상승한 경우가 더 많음.")
        print("     XOM은 에너지 섹터 특성상 RSI/MA 기반 타이밍이 잘 안 맞을 수 있음.")
    if len(rush_trades) > 5:
        print(f"  ⚠️  과잉 익절: Rush 신호가 {len(rush_trades)}회로 많음.")
        print("     주식 보유량이 지속 감소해 상승분을 제대로 포착하지 못했을 가능성.")
    print()


if __name__ == "__main__":
    main()
