"""
herd/backtest_weight.py — 거래량 가중치 재조정 백테스트

목적: 거래량 지표(volume_strength)의 선행성이 낮다는 분석 결과를 검증.
      가중치를 낮추거나 완전히 제거하고 선행 지표에 재배분했을 때
      수익률·MDD·신호 정확도가 어떻게 변화하는지 측정.

구성 A: 현재 v2 (volume_strength=10%)
구성 B: 거래량 절반 (volume_strength=5%, 잉여분 분배)
구성 C: 거래량 제거 (volume_strength=0%, 잉여분 분배)

Rush 정확도: Rush 신호 발생 후 3개월(63거래일) 뒤 주가가 하락한 비율
              → 높을수록 익절 신호가 정확함 (과열 판단 옳았음)
Flee 정확도: Flee 신호 발생 후 3개월(63거래일) 뒤 주가가 상승한 비율
              → 높을수록 매수 신호가 정확함 (공포 판단 옳았음)

전략: 트레일링 스탑
  Rush(≥75)  → 트레일링 스탑 설정 (고점 -8%, 60거래일, 30% 매도)
  Drift(60~75) → 즉시 5% 익절
  Flee(≤15)  → 즉시 30% 추가매수
  쿨다운: 20거래일
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

from collectors.stock_collector import collect                # noqa: E402
from indicators.rsi import calc_weekly_rsi, calc_monthly_rsi # noqa: E402
from indicators.price_position import (                      # noqa: E402
    calc_52w_position,
    calc_ma200_deviation,
)
from indicators.volume import calc_volume_strength           # noqa: E402
from indicators.ma200_weekly import calc_ma200_weekly        # noqa: E402

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════
# 비교할 3가지 가중치 구성
# ══════════════════════════════════════════════
CONFIGS: dict[str, dict[str, float]] = {
    "A (현재 v2)": {
        "monthly_rsi":     0.20,
        "weekly_rsi":      0.18,
        "position_52w":    0.18,
        "ma200_deviation": 0.14,
        "volume_strength": 0.10,
        "ma200_weekly":    0.20,
    },
    "B (거래량 절반)": {
        "monthly_rsi":     0.23,
        "weekly_rsi":      0.18,
        "position_52w":    0.18,
        "ma200_deviation": 0.17,
        "volume_strength": 0.05,
        "ma200_weekly":    0.19,
    },
    "C (거래량 제거)": {
        "monthly_rsi":     0.24,
        "weekly_rsi":      0.19,
        "position_52w":    0.19,
        "ma200_deviation": 0.18,
        "volume_strength": 0.00,
        "ma200_weekly":    0.20,
    },
}

# 가중치 합계 검증
for _name, _weights in CONFIGS.items():
    _total = round(sum(_weights.values()), 10)
    assert _total == 1.0, f"구성 '{_name}' 가중치 합계 오류: {_total}"

# 지표 이름 → 계산 함수
_INDICATOR_FUNCS: dict[str, callable] = {
    "monthly_rsi":     calc_monthly_rsi,
    "weekly_rsi":      calc_weekly_rsi,
    "position_52w":    calc_52w_position,
    "ma200_deviation": calc_ma200_deviation,
    "volume_strength": calc_volume_strength,
    "ma200_weekly":    calc_ma200_weekly,
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

# 신호 정확도 측정 기간: 신호 후 N거래일 뒤 주가 비교
ACCURACY_DAYS = 63  # 약 3개월

TICKERS     = ["NVDA", "MSFT", "KO", "JPM", "XOM", "SPY"]
DATA_PERIOD = "10y"
MIN_ROWS    = 252 + 21


# ══════════════════════════════════════════════
# 지표 시계열 사전 계산 (종목당 1회 — 3개 구성 공통)
# ══════════════════════════════════════════════
def _build_all_indicator_series(df: pd.DataFrame) -> dict[str, pd.Series]:
    """
    6개 지표 전부를 시계열로 계산해 반환한다.
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
    """
    사전 계산된 지표 시계열에 구성별 가중치를 적용해 HERD 시계열을 반환한다.
    가중치 0인 지표는 자동으로 기여분이 0이 됨.
    """
    herd: pd.Series | None = None
    for key, weight in weights.items():
        if weight == 0.0:
            continue
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
class WeightResult:
    """단일 구성 × 단일 종목 시뮬레이션 결과."""
    ticker:           str
    config_name:      str
    portfolio_values: list[float] = field(default_factory=list)

    # 신호 발생 시점 인덱스 기록 (정확도 계산용)
    rush_signal_idxs: list[int] = field(default_factory=list)
    flee_signal_idxs: list[int] = field(default_factory=list)

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

    def rush_count(self) -> int:
        return len(self.rush_signal_idxs)

    def flee_count(self) -> int:
        return len(self.flee_signal_idxs)

    def rush_accuracy(self, close: pd.Series) -> float:
        """
        Rush 신호 후 ACCURACY_DAYS 거래일 뒤 주가가 하락한 비율.
        → 높을수록 익절 타이밍이 정확함.
        """
        prices = close.values
        n = len(prices)
        correct = 0
        valid = 0
        for idx in self.rush_signal_idxs:
            future_idx = idx + ACCURACY_DAYS
            if future_idx < n:
                valid += 1
                if prices[future_idx] < prices[idx]:
                    correct += 1
        return (correct / valid * 100) if valid > 0 else float("nan")

    def flee_accuracy(self, close: pd.Series) -> float:
        """
        Flee 신호 후 ACCURACY_DAYS 거래일 뒤 주가가 상승한 비율.
        → 높을수록 매수 타이밍이 정확함.
        """
        prices = close.values
        n = len(prices)
        correct = 0
        valid = 0
        for idx in self.flee_signal_idxs:
            future_idx = idx + ACCURACY_DAYS
            if future_idx < n:
                valid += 1
                if prices[future_idx] > prices[idx]:
                    correct += 1
        return (correct / valid * 100) if valid > 0 else float("nan")


# ══════════════════════════════════════════════
# 트레일링 스탑 전략 실행
# ══════════════════════════════════════════════
def _run_trailing_stop(
    close: pd.Series,
    herd: pd.Series,
    ticker: str,
    config_name: str,
) -> WeightResult:
    result = WeightResult(ticker=ticker, config_name=config_name)
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
                cash, shares = _sell(cash, shares, price, TRAILING_SELL_RATIO)
                last_sell = i
                trailing_active = False
            elif trailing_days_left <= 0:
                trailing_active = False

        # ── HERD 신호 처리 ─────────────────────────────────────────────────
        if pd.notna(score):
            sell_ok = (i - last_sell) > SIGNAL_COOLDOWN
            buy_ok  = (i - last_buy)  > SIGNAL_COOLDOWN

            if score >= RUSH_THRESHOLD and shares > 0 and sell_ok:
                if not trailing_active:
                    trailing_active    = True
                    trailing_high      = price
                    trailing_days_left = TRAILING_MAX_DAYS
                    last_sell = i
                    result.rush_signal_idxs.append(i)  # 정확도 측정용 인덱스 기록

            elif DRIFT_LOWER <= score < RUSH_THRESHOLD and shares > 0 and sell_ok:
                cash, shares = _sell(cash, shares, price, DRIFT_SELL_RATIO)
                last_sell = i

            elif score <= FLEE_THRESHOLD and cash > 1.0 and buy_ok:
                cash, shares = _buy(cash, shares, price, FLEE_BUY_RATIO)
                last_buy = i
                result.flee_signal_idxs.append(i)  # 정확도 측정용 인덱스 기록

        result.portfolio_values.append(cash + shares * price)

    return result


# ══════════════════════════════════════════════
# 메인 — 백테스트 실행 및 결과 출력
# ══════════════════════════════════════════════
def _fmt(v: float) -> str:
    return f"{'+' if v >= 0 else ''}{v:.1f}%"


def _fmt_pct(v: float) -> str:
    """정확도 (항상 양수 %)"""
    if v != v:  # nan check
        return "   N/A"
    return f"{v:.1f}%"


def run_weight_backtest() -> None:
    print()
    print("═" * 100)
    print("  거래량 가중치 재조정 백테스트")
    print(f"  종목: {', '.join(TICKERS)}  |  기간: {DATA_PERIOD}")
    print(f"  전략: 트레일링 스탑  Rush≥{RUSH_THRESHOLD:.0f} / Flee≤{FLEE_THRESHOLD:.0f}")
    print(f"  신호 정확도 측정 기간: {ACCURACY_DAYS}거래일 후 (약 3개월)")
    print("═" * 100)

    # config_name → (결과 리스트, close 시리즈 리스트)
    all_results: dict[str, list[WeightResult]] = {name: [] for name in CONFIGS}
    close_series: list[pd.Series] = []  # 종목 순서대로 보관 (정확도 계산용)

    for ticker in TICKERS:
        print(f"\n  [{ticker}] 데이터 수집 + 지표 시계열 계산 중...", end=" ", flush=True)
        df = collect(ticker, period=DATA_PERIOD)
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date").sort_index()
        close = df["Close"]
        close_series.append(close)

        # 6개 지표 시계열을 1회만 계산 (3개 구성 공통)
        all_indicators = _build_all_indicator_series(df)
        print(f"{len(df)}일치 완료 ({close.index[0].date()} ~ {close.index[-1].date()})")

        for config_name, weights in CONFIGS.items():
            herd = _apply_weights(all_indicators, weights)
            result = _run_trailing_stop(close, herd, ticker, config_name)
            all_results[config_name].append(result)

            rush_acc = result.rush_accuracy(close)
            flee_acc = result.flee_accuracy(close)
            print(
                f"    {config_name:<18}  "
                f"수익률={_fmt(result.return_pct()):>7}  "
                f"MDD={result.mdd():>5.1f}%  "
                f"Rush={result.rush_count():>2}회({_fmt_pct(rush_acc):>5})  "
                f"Flee={result.flee_count():>2}회({_fmt_pct(flee_acc):>5})"
            )

    n = len(TICKERS)

    # ── 구성별 평균 요약 테이블 (핵심) ──────────────────────────────────────
    print()
    print("═" * 100)
    print("  === 구성별 평균 비교 요약 ===")
    print("═" * 100)
    print(
        f"  {'구성':<20}  {'평균 수익률':>10}  {'vs A':>7}  "
        f"{'평균 MDD':>9}  {'vs A':>7}  "
        f"{'Rush 정확도':>10}  {'Flee 정확도':>10}  "
        f"{'Rush 신호수':>9}  {'Flee 신호수':>9}"
    )
    print("  " + "─" * 96)

    # A 구성 기준값
    a_results = all_results["A (현재 v2)"]
    a_avg_ret = sum(r.return_pct() for r in a_results) / n
    a_avg_mdd = sum(r.mdd() for r in a_results) / n

    for config_name, results in all_results.items():
        avg_ret    = sum(r.return_pct() for r in results) / n
        avg_mdd    = sum(r.mdd() for r in results) / n
        total_rush = sum(r.rush_count() for r in results)
        total_flee = sum(r.flee_count() for r in results)
        vs_ret     = avg_ret - a_avg_ret
        vs_mdd     = avg_mdd - a_avg_mdd

        # Rush / Flee 정확도: 전체 신호에서 종합 계산 (유효 신호만 집계)
        rush_correct = 0
        rush_valid   = 0
        flee_correct = 0
        flee_valid   = 0
        for i, result in enumerate(results):
            cs = close_series[i]
            prices = cs.values
            n_prices = len(prices)
            for idx in result.rush_signal_idxs:
                future_idx = idx + ACCURACY_DAYS
                if future_idx < n_prices:
                    rush_valid += 1
                    if prices[future_idx] < prices[idx]:
                        rush_correct += 1
            for idx in result.flee_signal_idxs:
                future_idx = idx + ACCURACY_DAYS
                if future_idx < n_prices:
                    flee_valid += 1
                    if prices[future_idx] > prices[idx]:
                        flee_correct += 1

        rush_acc_avg = (rush_correct / rush_valid * 100) if rush_valid > 0 else float("nan")
        flee_acc_avg = (flee_correct / flee_valid * 100) if flee_valid > 0 else float("nan")

        is_baseline = config_name.startswith("A")
        vs_ret_str  = "  (기준)" if is_baseline else _fmt(vs_ret)
        vs_mdd_str  = "  (기준)" if is_baseline else _fmt(vs_mdd)

        print(
            f"  {config_name:<20}  {_fmt(avg_ret):>10}  {vs_ret_str:>7}  "
            f"{avg_mdd:>8.1f}%  {vs_mdd_str:>7}  "
            f"{_fmt_pct(rush_acc_avg):>10}  {_fmt_pct(flee_acc_avg):>10}  "
            f"{total_rush:>8}회  {total_flee:>8}회"
        )

    print()
    print("  ※ 해석 기준:")
    print("    수익률 vs A > 0   → 거래량 가중치 낮춰도 수익 개선")
    print("    MDD     vs A < 0  → MDD 개선 (낙폭 감소)")
    print(f"    Rush 정확도       → 신호 {ACCURACY_DAYS}거래일 후 주가 하락 비율 (높을수록 익절 타이밍 정확)")
    print(f"    Flee 정확도       → 신호 {ACCURACY_DAYS}거래일 후 주가 상승 비율 (높을수록 매수 타이밍 정확)")

    # ── 종목별 상세 테이블 ────────────────────────────────────────────────
    print()
    print("═" * 100)
    print("  === 종목별 수익률 / MDD 상세 ===")
    print("═" * 100)
    short_names = [name.split(" ")[0] for name in CONFIGS.keys()]  # A, B, C
    print(
        f"  {'종목':<6}  "
        + "  ".join(f"{'['+s+']수익':>8}  {'['+s+']MDD':>7}" for s in short_names)
    )
    print("  " + "─" * 70)

    config_result_lists = list(all_results.values())
    for i, ticker in enumerate(TICKERS):
        row = f"  {ticker:<6}  "
        row += "  ".join(
            f"{_fmt(results[i].return_pct()):>8}  {results[i].mdd():>6.1f}%"
            for results in config_result_lists
        )
        print(row)

    # ── Rush / Flee 신호 수 + 정확도 종목별 상세 ────────────────────────
    print()
    print("═" * 100)
    print("  === 종목별 신호 수 / 정확도 상세 ===")
    print("═" * 100)
    print(
        f"  {'종목':<6}  "
        + "  ".join(
            f"{'['+s+']Rush':>5} {'정확':>5}  {'['+s+']Flee':>5} {'정확':>5}"
            for s in short_names
        )
    )
    print("  " + "─" * 85)

    for i, ticker in enumerate(TICKERS):
        cs = close_series[i]
        row = f"  {ticker:<6}  "
        parts = []
        for results in config_result_lists:
            r = results[i]
            rush_a = _fmt_pct(r.rush_accuracy(cs))
            flee_a = _fmt_pct(r.flee_accuracy(cs))
            parts.append(f"{r.rush_count():>4}회 {rush_a:>5}  {r.flee_count():>4}회 {flee_a:>5}")
        row += "  ".join(parts)
        print(row)

    print()


if __name__ == "__main__":
    run_weight_backtest()
