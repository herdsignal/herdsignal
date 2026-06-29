"""
herd/backtest_bollinger.py — 볼린저밴드 추가 전후 성능 비교 백테스트

v2  (6개 지표 기준선) vs v2+ (볼린저밴드 추가 7개 지표) 비교.

전략: 트레일링 스탑 (EPS 필터 없음 — 순수 지표 효과 비교)
  Rush(≥75)    → 트레일링 스탑 (-8%, 60거래일, 30% 매도)
  Drift(60~75) → 즉시 5% 익절
  Flee(≤15)    → 즉시 30% 추가매수
  쿨다운: 20거래일

최적화: 7개 지표 시계열을 종목당 1회 계산 후 구성별 가중치만 다르게 적용.
"""

import logging
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from collectors.stock_collector import collect                      # noqa: E402
from indicators.rsi import calc_weekly_rsi, calc_monthly_rsi       # noqa: E402
from indicators.price_position import (                             # noqa: E402
    calc_52w_position,
    calc_ma200_deviation,
)
from indicators.volume import calc_volume_strength                  # noqa: E402
from indicators.ma200_weekly import calc_ma200_weekly               # noqa: E402
from indicators.bollinger import calc_bollinger_pct_b               # noqa: E402

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════
# 비교 구성
# ══════════════════════════════════════════════
CONFIGS: dict[str, dict[str, float]] = {
    "v2 (6개 기준선)": {
        "monthly_rsi":     0.20,
        "weekly_rsi":      0.18,
        "position_52w":    0.18,
        "ma200_deviation": 0.14,
        "volume_strength": 0.10,
        "ma200_weekly":    0.20,
    },
    "v2+ (볼린저 추가)": {
        "monthly_rsi":     0.18,
        "weekly_rsi":      0.16,
        "position_52w":    0.16,
        "ma200_deviation": 0.12,
        "volume_strength": 0.08,
        "ma200_weekly":    0.18,
        "bollinger":       0.12,
    },
}

# 가중치 합계 검증 — 합이 1.0이 아니면 즉시 오류
for _name, _weights in CONFIGS.items():
    _total = round(sum(_weights.values()), 10)
    assert _total == 1.0, f"구성 '{_name}' 가중치 합계 오류: {_total}"

# 지표 이름 → 계산 함수 (config 키와 동일하게 맞춤)
_INDICATOR_FUNCS: dict[str, callable] = {
    "monthly_rsi":     calc_monthly_rsi,
    "weekly_rsi":      calc_weekly_rsi,
    "position_52w":    calc_52w_position,
    "ma200_deviation": calc_ma200_deviation,
    "volume_strength": calc_volume_strength,
    "ma200_weekly":    calc_ma200_weekly,
    "bollinger":       calc_bollinger_pct_b,   # 신규 — 변동성 기반 군중 쏠림
}


# ──────────────────────────────────────────────
# 전략 파라미터
# ──────────────────────────────────────────────
INITIAL_CASH       = 10_000.0
FEE_RATE           = 0.001

RUSH_THRESHOLD     = 75.0
DRIFT_LOWER        = 60.0
FLEE_THRESHOLD     = 15.0
SIGNAL_COOLDOWN    = 20

DRIFT_SELL_RATIO   = 0.05
FLEE_BUY_RATIO     = 0.30
TRAILING_STOP_PCT  = 0.08
TRAILING_MAX_DAYS  = 60
TRAILING_SELL_RATIO = 0.30

TICKERS     = ["NVDA", "MSFT", "KO", "JPM", "SPY"]
DATA_PERIOD = "10y"
MIN_ROWS    = 252 + 21  # MA200 계산에 필요한 최소 행 수 + 여유분


# ══════════════════════════════════════════════
# 지표 시계열 사전 계산 (종목당 1회 — 모든 구성 공통)
# ══════════════════════════════════════════════
def _build_all_indicator_series(df: pd.DataFrame) -> dict[str, pd.Series]:
    """
    7개 지표 전부를 시계열로 계산해 반환한다.
    한 번만 계산하면 v2·v2+ 구성 모두 가중치만 다르게 적용 가능.

    look-ahead bias 방지: i번째 날까지의 슬라이스만 각 지표 함수에 전달.
    """
    raw: dict[str, dict] = {key: {} for key in _INDICATOR_FUNCS}

    for i in range(MIN_ROWS, len(df)):
        slice_df = df.iloc[: i + 1].copy()
        date = df.index[i]

        for key, func in _INDICATOR_FUNCS.items():
            try:
                raw[key][date] = func(slice_df)
            except Exception:
                raw[key][date] = float("nan")

    return {key: pd.Series(vals, name=key) for key, vals in raw.items()}


def _apply_weights(
    all_indicators: dict[str, pd.Series],
    weights: dict[str, float],
) -> pd.Series:
    """사전 계산된 지표 시계열에 구성별 가중치를 적용해 HERD 시계열을 반환한다."""
    herd: pd.Series | None = None
    for key, weight in weights.items():
        weighted = all_indicators[key] * weight
        herd = weighted if herd is None else herd + weighted
    return herd.clip(0, 100).round(2)  # type: ignore[union-attr]


# ══════════════════════════════════════════════
# 매매 헬퍼
# ══════════════════════════════════════════════
def _buy(cash: float, shares: float, price: float, ratio: float) -> tuple[float, float]:
    spend = cash * ratio
    return cash - spend, shares + (spend / (1 + FEE_RATE)) / price


def _sell(cash: float, shares: float, price: float, ratio: float) -> tuple[float, float]:
    sell_shares = shares * ratio
    return cash + sell_shares * price * (1 - FEE_RATE), shares - sell_shares


# ══════════════════════════════════════════════
# 결과 자료구조
# ══════════════════════════════════════════════
@dataclass
class BtResult:
    """단일 구성 × 단일 종목 시뮬레이션 결과."""
    ticker:           str
    config_name:      str
    portfolio_values: list[float] = field(default_factory=list)
    rush_signals:     int = 0
    flee_signals:     int = 0

    def final(self) -> float:
        return self.portfolio_values[-1] if self.portfolio_values else INITIAL_CASH

    def return_pct(self) -> float:
        return (self.final() / INITIAL_CASH - 1) * 100

    def mdd(self) -> float:
        peak = INITIAL_CASH
        max_dd = 0.0
        for v in self.portfolio_values:
            if v > peak:
                peak = v
            dd = (v - peak) / peak * 100
            if dd < max_dd:
                max_dd = dd
        return max_dd


# ══════════════════════════════════════════════
# 전략 — 트레일링 스탑 (EPS 필터 없음)
# ══════════════════════════════════════════════
def _run_trailing_stop(
    close: pd.Series,
    herd: pd.Series,
    ticker: str,
    config_name: str,
) -> BtResult:
    """
    트레일링 스탑 전략 시뮬레이션.
    EPS 필터 없이 Rush 발생 시 모두 트레일링 스탑으로 처리해
    순수하게 지표 구성 변화의 효과만 비교한다.
    """
    result = BtResult(ticker=ticker, config_name=config_name)
    price0 = float(close.iloc[0])
    cash, shares = _buy(INITIAL_CASH, 0.0, price0, 1.0)

    last_sell = -SIGNAL_COOLDOWN - 1
    last_buy  = -SIGNAL_COOLDOWN - 1

    trailing_active    = False
    trailing_high      = 0.0
    trailing_days_left = 0

    for i, (date, price) in enumerate(close.items()):
        price = float(price)
        score = float(herd.get(date, float("nan")))

        # ── 트레일링 스탑 상태 업데이트 ───────────────────────────────────
        if trailing_active:
            if price > trailing_high:
                trailing_high = price
            trailing_days_left -= 1
            stop_price = trailing_high * (1 - TRAILING_STOP_PCT)

            if price <= stop_price:
                # 스탑 발동 → 30% 매도
                cash, shares = _sell(cash, shares, price, TRAILING_SELL_RATIO)
                last_sell = i
                trailing_active = False
            elif trailing_days_left <= 0:
                # 60거래일 만료 → 보유 유지
                trailing_active = False

        # ── HERD 신호 처리 ─────────────────────────────────────────────────
        if pd.notna(score):
            sell_ok = (i - last_sell) > SIGNAL_COOLDOWN
            buy_ok  = (i - last_buy)  > SIGNAL_COOLDOWN

            if score >= RUSH_THRESHOLD and shares > 0 and sell_ok:
                # Rush → 트레일링 스탑 설정 (이미 활성 중이면 스킵)
                if not trailing_active:
                    trailing_active    = True
                    trailing_high      = price
                    trailing_days_left = TRAILING_MAX_DAYS
                    last_sell = i
                    result.rush_signals += 1

            elif DRIFT_LOWER <= score < RUSH_THRESHOLD and shares > 0 and sell_ok:
                # Drift → 즉시 5% 익절
                cash, shares = _sell(cash, shares, price, DRIFT_SELL_RATIO)
                last_sell = i

            elif score <= FLEE_THRESHOLD and cash > 1.0 and buy_ok:
                # Flee → 30% 추가매수
                cash, shares = _buy(cash, shares, price, FLEE_BUY_RATIO)
                last_buy = i
                result.flee_signals += 1

        result.portfolio_values.append(cash + shares * price)

    return result


# ══════════════════════════════════════════════
# 메인 — 전체 백테스트 실행 및 결과 출력
# ══════════════════════════════════════════════
def _fmt(v: float) -> str:
    return f"{'+' if v >= 0 else ''}{v:.1f}%"


def run_bollinger_backtest() -> None:
    print()
    print("═" * 90)
    print("  볼린저밴드 추가 전후 성능 비교 백테스트")
    print(f"  종목: {', '.join(TICKERS)}  |  기간: {DATA_PERIOD}")
    print(f"  전략: 트레일링 스탑  Rush≥{RUSH_THRESHOLD:.0f} / Flee≤{FLEE_THRESHOLD:.0f}")
    print(f"  트레일링 스탑: 고점 -{TRAILING_STOP_PCT*100:.0f}% / 최대 {TRAILING_MAX_DAYS}거래일")
    print("═" * 90)
    print()
    print("  구성 비교:")
    for name, weights in CONFIGS.items():
        print(f"    [{name}]  지표 {len(weights)}개  {list(weights.keys())}")
    print()

    # config_name → 종목별 결과 리스트 (TICKERS 순서 유지)
    all_results: dict[str, list[BtResult]] = {name: [] for name in CONFIGS}

    for ticker in TICKERS:
        print(f"  [{ticker}] 데이터 수집 + 지표 시계열 계산 중...", end=" ", flush=True)
        df = collect(ticker, period=DATA_PERIOD)
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date").sort_index()
        close = df["Close"]

        # 7개 지표 시계열을 1회만 계산 (v2·v2+ 공통)
        all_indicators = _build_all_indicator_series(df)
        print(f"{len(df)}일치 완료 ({close.index[0].date()} ~ {close.index[-1].date()})")

        for config_name, weights in CONFIGS.items():
            herd = _apply_weights(all_indicators, weights)
            result = _run_trailing_stop(close, herd, ticker, config_name)
            all_results[config_name].append(result)

            print(
                f"    {config_name:<20}  "
                f"수익률={_fmt(result.return_pct()):>7}  "
                f"MDD={result.mdd():>5.1f}%  "
                f"Rush={result.rush_signals:>2}회  Flee={result.flee_signals:>2}회"
            )

    n = len(TICKERS)

    # ── 구성별 평균 요약 ───────────────────────────────────────────────────
    print()
    print("═" * 90)
    print("  === 볼린저밴드 추가 효과 요약 ===")
    print("═" * 90)
    print(
        f"  {'구성':<22}  {'평균 수익률':>10}  {'vs v2':>8}  "
        f"{'평균 MDD':>9}  {'vs v2':>8}  {'Rush':>6}  {'Flee':>6}"
    )
    print("  " + "─" * 85)

    # v2 기준값 계산
    v2_results = all_results["v2 (6개 기준선)"]
    v2_avg_ret = sum(r.return_pct() for r in v2_results) / n
    v2_avg_mdd = sum(r.mdd() for r in v2_results) / n

    for config_name, results in all_results.items():
        avg_ret    = sum(r.return_pct() for r in results) / n
        avg_mdd    = sum(r.mdd() for r in results) / n
        total_rush = sum(r.rush_signals for r in results)
        total_flee = sum(r.flee_signals for r in results)
        is_baseline = config_name.startswith("v2 (")

        vs_ret_str = "  (기준)" if is_baseline else _fmt(avg_ret - v2_avg_ret)
        vs_mdd_str = "  (기준)" if is_baseline else _fmt(avg_mdd - v2_avg_mdd)

        print(
            f"  {config_name:<22}  {_fmt(avg_ret):>10}  {vs_ret_str:>8}  "
            f"{avg_mdd:>8.1f}%  {vs_mdd_str:>8}  "
            f"{total_rush:>5}회  {total_flee:>5}회"
        )

    print()
    print("  ※ vs v2 해석:")
    print("    수익률 > 0  → 볼린저밴드 추가 후 수익 개선 (추가 효과 있음)")
    print("    MDD    < 0  → 볼린저밴드 추가 후 MDD 개선 (낙폭 축소)")

    # ── 종목별 상세 테이블 ─────────────────────────────────────────────────
    print()
    print("═" * 90)
    print("  === 종목별 상세 비교 ===")
    print("═" * 90)
    print(
        f"  {'종목':<6}  "
        f"{'[v2]수익':>9}  {'[v2]MDD':>8}  {'[v2+]수익':>10}  {'[v2+]MDD':>9}  "
        f"{'수익차':>7}  {'MDD차':>7}  "
        f"{'v2 Rush/Flee':>13}  {'v2+ Rush/Flee':>14}"
    )
    print("  " + "─" * 88)

    v2_list  = all_results["v2 (6개 기준선)"]
    vp_list  = all_results["v2+ (볼린저 추가)"]

    for i, ticker in enumerate(TICKERS):
        v2  = v2_list[i]
        vp  = vp_list[i]
        d_ret = vp.return_pct() - v2.return_pct()
        d_mdd = vp.mdd() - v2.mdd()

        print(
            f"  {ticker:<6}  "
            f"{_fmt(v2.return_pct()):>9}  {v2.mdd():>7.1f}%  "
            f"{_fmt(vp.return_pct()):>10}  {vp.mdd():>8.1f}%  "
            f"{_fmt(d_ret):>7}  {_fmt(d_mdd):>7}  "
            f"{v2.rush_signals:>4}회/{v2.flee_signals:>3}회  "
            f"{vp.rush_signals:>5}회/{vp.flee_signals:>3}회"
        )

    print()


if __name__ == "__main__":
    run_bollinger_backtest()
