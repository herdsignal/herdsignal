"""
herd/backtest_v3.py — HERD v3: 실적 서프라이즈 필터 + 트레일링 스탑 백테스트

전략 A — Buy & Hold (기준선)
전략 B — HERD v2 (Rush 즉시 30% 익절)
전략 C — HERD v3 (Rush 예외 판단 + 트레일링 스탑)
  Rush 신호 발생 시:
    EPS 서프라이즈 ≥ 10% → Momentum Rush (익절 보류, 상승 모멘텀 유지)
    EPS 서프라이즈 < 10% 또는 데이터 없음 → Crowd Rush (트레일링 스탑 -8%, 60거래일)
  Flee 신호: 기존과 동일 (현금 30% 추가매수)
  Drift 신호: 기존과 동일 (보유 5% 익절)

주의:
  - Finnhub 무료 플랜은 최근 4분기 실적만 제공 → 10년 백테스트 초반은 서프라이즈 없음으로 처리
  - look-ahead bias 방지: 분기 마감 + 45일 이후부터만 해당 분기 실적 데이터 사용
"""

import logging
import sys
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from collectors.stock_collector import collect                          # noqa: E402
from collectors.finnhub_collector import (                             # noqa: E402
    get_earnings_history,
    get_surprise_at_date,
)
from herd.backtest import _build_herd_series                           # noqa: E402

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 백테스트 파라미터
# ──────────────────────────────────────────────
INITIAL_CASH     = 10_000.0   # 초기 자금
FEE_RATE         = 0.001      # 수수료 0.1%

RUSH_THRESHOLD   = 75.0       # Rush 임계값
DRIFT_LOWER      = 60.0       # Drift 하한
FLEE_THRESHOLD   = 15.0       # Flee 임계값

SIGNAL_COOLDOWN  = 20         # 동방향 신호 중복 제거 (거래일)
RUSH_SELL_RATIO  = 0.30       # Rush 익절 비율
DRIFT_SELL_RATIO = 0.05       # Drift 익절 비율
FLEE_BUY_RATIO   = 0.30       # Flee 추가매수 비율

# 전략 C 고유 파라미터
MOMENTUM_RUSH_MIN_SURPRISE = 10.0  # Momentum Rush 판정 EPS 서프라이즈 최솟값 (%)
TRAILING_STOP_PCT          = 0.08  # 고점 대비 하락률 트레일링 스탑 기준 (8%)
TRAILING_MAX_DAYS          = 60    # 트레일링 스탑 최대 대기 기간 (거래일)
TRAILING_SELL_RATIO        = 0.30  # 트레일링 스탑 발동 시 매도 비율

TICKERS = ["NVDA", "MSFT", "AAPL", "JPM", "SPY"]
DATA_PERIOD = "10y"


# ──────────────────────────────────────────────
# 결과 자료구조
# ──────────────────────────────────────────────
@dataclass
class StratResult:
    """단일 전략 시뮬레이션 결과."""
    name:             str
    portfolio_values: list[float] = field(default_factory=list)

    def final(self) -> float:
        return self.portfolio_values[-1] if self.portfolio_values else INITIAL_CASH

    def return_pct(self) -> float:
        return (self.final() / INITIAL_CASH - 1) * 100

    def mdd(self) -> float:
        """최대 낙폭(MDD) 계산."""
        peak   = INITIAL_CASH
        max_dd = 0.0
        for v in self.portfolio_values:
            if v > peak:
                peak = v
            dd = (v - peak) / peak * 100
            if dd < max_dd:
                max_dd = dd
        return max_dd


@dataclass
class StratCStats:
    """전략 C 특화 통계 (Momentum Rush / 트레일링 스탑)."""
    momentum_rush_count:       int         = 0   # Momentum Rush 발동 (익절 보류)
    crowd_rush_count:          int         = 0   # Crowd Rush 발동 (트레일링 스탑 설정)
    trailing_triggered_count:  int         = 0   # 트레일링 스탑 실제 발동
    trailing_expired_count:    int         = 0   # 트레일링 스탑 만료 (60일 미발동)
    # 트레일링 스탑 발동 시: (Rush 신호 가격 → 스탑 발동 가격) 수익률
    trailing_entry_returns:    list[float] = field(default_factory=list)


# ──────────────────────────────────────────────
# 공통 매매 헬퍼
# ──────────────────────────────────────────────
def _buy(cash: float, shares: float, price: float, ratio: float) -> tuple[float, float]:
    """현금 ratio 비율로 매수 (수수료 포함)."""
    spend = cash * ratio
    new_shares = (spend / (1 + FEE_RATE)) / price
    return cash - spend, shares + new_shares


def _sell(cash: float, shares: float, price: float, ratio: float) -> tuple[float, float]:
    """주식 ratio 비율을 매도 (수수료 포함)."""
    sell_shares = shares * ratio
    proceeds    = sell_shares * price * (1 - FEE_RATE)
    return cash + proceeds, shares - sell_shares


# ──────────────────────────────────────────────
# 전략 A — Buy & Hold
# ──────────────────────────────────────────────
def _run_strategy_a(close: pd.Series) -> StratResult:
    """시작일 전액 매수 후 만기까지 보유."""
    result = StratResult(name="A-BuyHold")
    price0 = float(close.iloc[0])
    cash, shares = _buy(INITIAL_CASH, 0.0, price0, ratio=1.0)
    for price in close:
        result.portfolio_values.append(cash + shares * float(price))
    return result


# ──────────────────────────────────────────────
# 전략 B — HERD v2 (Rush 즉시 30% 익절)
# ──────────────────────────────────────────────
def _run_strategy_b(close: pd.Series, herd: pd.Series) -> StratResult:
    """
    Rush → 즉시 30% 익절
    Drift → 즉시 5% 익절
    Flee  → 즉시 30% 추가매수
    20거래일 쿨다운 적용.
    """
    result = StratResult(name="B-HERDv2")
    price0 = float(close.iloc[0])
    cash, shares = _buy(INITIAL_CASH, 0.0, price0, ratio=1.0)

    last_sell_pos = -SIGNAL_COOLDOWN - 1
    last_buy_pos  = -SIGNAL_COOLDOWN - 1

    for i, (date, price) in enumerate(close.items()):
        price = float(price)
        score = float(herd.get(date, float("nan")))

        if pd.notna(score):
            sell_ok = (i - last_sell_pos) > SIGNAL_COOLDOWN
            buy_ok  = (i - last_buy_pos)  > SIGNAL_COOLDOWN

            if score >= RUSH_THRESHOLD and shares > 0 and sell_ok:
                # Rush → 즉시 30% 익절
                cash, shares = _sell(cash, shares, price, RUSH_SELL_RATIO)
                last_sell_pos = i

            elif DRIFT_LOWER <= score < RUSH_THRESHOLD and shares > 0 and sell_ok:
                # Drift → 즉시 5% 익절
                cash, shares = _sell(cash, shares, price, DRIFT_SELL_RATIO)
                last_sell_pos = i

            elif score <= FLEE_THRESHOLD and cash > 1.0 and buy_ok:
                # Flee → 30% 추가매수
                cash, shares = _buy(cash, shares, price, FLEE_BUY_RATIO)
                last_buy_pos = i

        result.portfolio_values.append(cash + shares * price)

    return result


# ──────────────────────────────────────────────
# 전략 C — HERD v3 (Rush 예외 판단 + 트레일링 스탑)
# ──────────────────────────────────────────────
def _run_strategy_c(
    close: pd.Series,
    herd:  pd.Series,
    earnings_history: list[dict],
) -> tuple[StratResult, StratCStats]:
    """
    Rush 신호 발생 시 실적 서프라이즈를 체크해 두 가지 경로로 분기한다.

    Momentum Rush (서프라이즈 ≥ 10%):
      즉시 익절하지 않고 보유 유지. 상승 모멘텀이 지속될 것으로 판단.

    Crowd Rush (서프라이즈 < 10% 또는 데이터 없음):
      즉시 팔지 않고 트레일링 스탑을 설정.
      고점 대비 -8% 하락 시 30% 익절.
      60거래일 내 스탑 미발동 시 보유 유지.

    Drift / Flee: 기존 전략 B와 동일.
    """
    result = StratResult(name="C-HERDv3")
    stats  = StratCStats()

    price0 = float(close.iloc[0])
    cash, shares = _buy(INITIAL_CASH, 0.0, price0, ratio=1.0)

    last_sell_pos = -SIGNAL_COOLDOWN - 1
    last_buy_pos  = -SIGNAL_COOLDOWN - 1

    # 트레일링 스탑 상태
    trailing_active       = False
    trailing_high         = 0.0
    trailing_entry_price  = 0.0
    trailing_days_left    = 0

    for i, (date, price) in enumerate(close.items()):
        price    = float(price)
        score    = float(herd.get(date, float("nan")))
        date_dt  = date.to_pydatetime()

        # ── 1. 트레일링 스탑 체크 (신호 처리 전에 먼저 실행) ──────────────
        if trailing_active:
            # 고점 갱신
            if price > trailing_high:
                trailing_high = price

            trailing_days_left -= 1
            stop_price = trailing_high * (1 - TRAILING_STOP_PCT)

            if price <= stop_price:
                # 트레일링 스탑 발동 → 30% 매도
                cash, shares = _sell(cash, shares, price, TRAILING_SELL_RATIO)
                last_sell_pos = i
                trailing_active = False

                # 통계 기록: Rush 신호 가격 → 스탑 발동 가격 수익률
                entry_return = (price - trailing_entry_price) / trailing_entry_price * 100
                stats.trailing_entry_returns.append(round(entry_return, 2))
                stats.trailing_triggered_count += 1

            elif trailing_days_left <= 0:
                # 60거래일 경과 → 스탑 만료, 보유 유지
                trailing_active = False
                stats.trailing_expired_count += 1

        # ── 2. 정규 HERD 신호 처리 ────────────────────────────────────────
        if pd.notna(score):
            sell_ok = (i - last_sell_pos) > SIGNAL_COOLDOWN
            buy_ok  = (i - last_buy_pos)  > SIGNAL_COOLDOWN

            if score >= RUSH_THRESHOLD and shares > 0 and sell_ok:
                # Rush 신호 — look-ahead bias 방지로 당시 사용 가능한 실적 조회
                surprise = get_surprise_at_date(earnings_history, date_dt)

                if surprise is not None and surprise >= MOMENTUM_RUSH_MIN_SURPRISE:
                    # Momentum Rush: 상승 모멘텀 유지 — 익절 보류
                    stats.momentum_rush_count += 1
                    last_sell_pos = i   # 쿨다운은 걸어 과도한 신호 재발 방지

                else:
                    # Crowd Rush: 트레일링 스탑 설정 (이미 활성 중이면 스킵)
                    if not trailing_active:
                        trailing_active      = True
                        trailing_high        = price
                        trailing_entry_price = price
                        trailing_days_left   = TRAILING_MAX_DAYS
                        stats.crowd_rush_count += 1
                        last_sell_pos = i

            elif DRIFT_LOWER <= score < RUSH_THRESHOLD and shares > 0 and sell_ok:
                # Drift → 즉시 5% 익절 (전략 B와 동일)
                cash, shares = _sell(cash, shares, price, DRIFT_SELL_RATIO)
                last_sell_pos = i

            elif score <= FLEE_THRESHOLD and cash > 1.0 and buy_ok:
                # Flee → 30% 추가매수 (전략 B와 동일)
                cash, shares = _buy(cash, shares, price, FLEE_BUY_RATIO)
                last_buy_pos = i

        result.portfolio_values.append(cash + shares * price)

    return result, stats


# ──────────────────────────────────────────────
# 종목 단위 실행
# ──────────────────────────────────────────────
def run_backtest_v3(ticker: str) -> dict:
    """
    단일 종목에 대해 전략 A/B/C를 실행하고 결과 딕셔너리를 반환한다.

    Returns:
        {
            "ticker": str,
            "a": StratResult, "b": StratResult, "c": StratResult,
            "stats": StratCStats,
            "start": str, "end": str,
        }
    """
    print(f"\n  [{ticker}] 데이터 수집 중...", end=" ", flush=True)

    # 10년 일봉 데이터 수집
    df = collect(ticker, period=DATA_PERIOD)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()
    close = df["Close"]
    print(f"{len(df)}일 ({close.index[0].date()} ~ {close.index[-1].date()})")

    # HERD v2 시계열 산출 (시간 소요)
    print(f"  [{ticker}] HERD 시계열 산출 중...", end=" ", flush=True)
    herd = _build_herd_series(df)
    print(f"완료 ({len(herd.dropna())}개 포인트)")

    # Finnhub 실적 히스토리 (전략 C용)
    print(f"  [{ticker}] Finnhub 실적 조회...", end=" ", flush=True)
    earnings = get_earnings_history(ticker)
    print(f"{len(earnings)}개 분기")

    # 전략 실행
    a = _run_strategy_a(close)
    b = _run_strategy_b(close, herd)
    c, stats = _run_strategy_c(close, herd, earnings)

    return {
        "ticker": ticker,
        "a":      a,
        "b":      b,
        "c":      c,
        "stats":  stats,
        "start":  close.index[0].strftime("%Y-%m-%d"),
        "end":    close.index[-1].strftime("%Y-%m-%d"),
    }


# ──────────────────────────────────────────────
# 결과 출력
# ──────────────────────────────────────────────
def _fmt(v: float) -> str:
    return f"{'+' if v >= 0 else ''}{v:.1f}%"


def print_results(all_results: list[dict]) -> None:
    """전체 백테스트 결과를 지정 형식으로 출력한다."""

    # ── 종목별 결과 테이블 ─────────────────────────
    print()
    print("═" * 84)
    print("  === 종목별 결과 ===")
    print("═" * 84)
    header = (
        f"  {'종목':<6}  {'A수익':>8}  {'B수익':>8}  {'C수익':>8}  "
        f"{'A MDD':>8}  {'C MDD':>8}  {'B→C변화':>9}  {'MDD개선':>8}"
    )
    print(header)
    print("  " + "─" * 80)

    sum_a = sum_b = sum_c = sum_amdd = sum_cmdd = 0.0

    for r in all_results:
        a_ret  = r["a"].return_pct()
        b_ret  = r["b"].return_pct()
        c_ret  = r["c"].return_pct()
        a_mdd  = r["a"].mdd()
        c_mdd  = r["c"].mdd()
        bc_chg = c_ret - b_ret                  # B→C 수익률 변화
        mdd_impv = c_mdd - a_mdd               # MDD 개선 (양수 = 낙폭 감소 = 개선)

        sum_a    += a_ret;  sum_b += b_ret;  sum_c += c_ret
        sum_amdd += a_mdd;  sum_cmdd += c_mdd

        mdd_mark = "▼개선" if mdd_impv > 0 else "▲악화"
        print(
            f"  {r['ticker']:<6}  {_fmt(a_ret):>8}  {_fmt(b_ret):>8}  {_fmt(c_ret):>8}  "
            f"{_fmt(a_mdd):>8}  {_fmt(c_mdd):>8}  {_fmt(bc_chg):>9}  {mdd_mark:>8}"
        )

    n = len(all_results)
    print("  " + "─" * 80)
    print(
        f"  {'평균':<6}  {_fmt(sum_a/n):>8}  {_fmt(sum_b/n):>8}  {_fmt(sum_c/n):>8}  "
        f"{_fmt(sum_amdd/n):>8}  {_fmt(sum_cmdd/n):>8}  "
        f"{_fmt((sum_c-sum_b)/n):>9}  {'':>8}"
    )

    # ── 전략 C 핵심 지표 ───────────────────────────
    print()
    print("═" * 84)
    print("  === 전략 C 핵심 지표 ===")
    print("═" * 84)
    print(
        f"  {'종목':<6}  {'Momentum Rush':>15}  {'Crowd Rush':>12}  "
        f"{'스탑 발동':>10}  {'스탑 만료':>10}  {'발동 평균수익':>14}"
    )
    print("  " + "─" * 80)

    total_mom = total_crowd = total_trig = total_exp = 0
    all_trig_returns: list[float] = []

    for r in all_results:
        s = r["stats"]
        avg_trig = (
            f"{sum(s.trailing_entry_returns)/len(s.trailing_entry_returns):+.1f}%"
            if s.trailing_entry_returns else "  N/A"
        )
        print(
            f"  {r['ticker']:<6}  {s.momentum_rush_count:>15}회  "
            f"{s.crowd_rush_count:>10}회  "
            f"{s.trailing_triggered_count:>8}회  "
            f"{s.trailing_expired_count:>8}회  "
            f"{avg_trig:>14}"
        )
        total_mom   += s.momentum_rush_count
        total_crowd += s.crowd_rush_count
        total_trig  += s.trailing_triggered_count
        total_exp   += s.trailing_expired_count
        all_trig_returns.extend(s.trailing_entry_returns)

    print("  " + "─" * 80)
    overall_avg = (
        f"{sum(all_trig_returns)/len(all_trig_returns):+.1f}%"
        if all_trig_returns else "  N/A"
    )
    print(
        f"  {'합계':<6}  {total_mom:>15}회  {total_crowd:>10}회  "
        f"{total_trig:>8}회  {total_exp:>8}회  {overall_avg:>14}"
    )

    # ── 전체 평균 요약 ─────────────────────────────
    print()
    print("═" * 84)
    print("  === 전체 평균 요약 ===")
    print("═" * 84)
    print(f"  전략 A (Buy & Hold)       평균 수익: {_fmt(sum_a/n)}  평균 MDD: {_fmt(sum_amdd/n)}")
    print(f"  전략 B (HERD v2 즉시익절) 평균 수익: {_fmt(sum_b/n)}")
    print(f"  전략 C (HERD v3 트레일링) 평균 수익: {_fmt(sum_c/n)}  평균 MDD: {_fmt(sum_cmdd/n)}")
    print()
    print(f"  B→C 수익률 변화: {_fmt((sum_c-sum_b)/n)} (양수 = C가 더 유리)")
    print(f"  C vs A MDD 개선: {_fmt((sum_cmdd-sum_amdd)/n)} (양수 = MDD 감소 = 개선)")
    print()
    print("  ⚠️  Finnhub 무료 플랜은 최근 4분기 실적만 제공")
    print("     → 10년 백테스트 초반 9년은 실적 데이터 없음 → 전부 Crowd Rush 처리")
    print("     → Momentum Rush 효과 관찰을 위해서는 프리미엄 플랜 필요")
    print()


# ──────────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────────
def main() -> None:
    print()
    print("═" * 84)
    print("  HERD v3 백테스트 — 실적 서프라이즈 필터 + 트레일링 스탑")
    print(f"  종목: {', '.join(TICKERS)}")
    print(f"  기간: {DATA_PERIOD}  |  Rush≥{RUSH_THRESHOLD:.0f} / Flee≤{FLEE_THRESHOLD:.0f}")
    print(
        f"  Momentum Rush 기준: EPS 서프라이즈 ≥ {MOMENTUM_RUSH_MIN_SURPRISE:.0f}%"
    )
    print(
        f"  트레일링 스탑: 고점 대비 -{TRAILING_STOP_PCT*100:.0f}%, "
        f"최대 {TRAILING_MAX_DAYS}거래일"
    )
    print("═" * 84)

    all_results: list[dict] = []

    for ticker in TICKERS:
        try:
            result = run_backtest_v3(ticker)
            all_results.append(result)
            a = result["a"]
            b = result["b"]
            c = result["c"]
            print(
                f"  [{ticker}] 완료 — "
                f"A: {_fmt(a.return_pct())} | "
                f"B: {_fmt(b.return_pct())} | "
                f"C: {_fmt(c.return_pct())}"
            )
        except Exception as e:
            print(f"  [{ticker}] ❌ 오류: {e}")

    if all_results:
        print_results(all_results)
    else:
        print("  결과 없음")


if __name__ == "__main__":
    main()
