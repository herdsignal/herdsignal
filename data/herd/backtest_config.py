"""
herd/backtest_config.py — 지표 구성별 성능 비교 백테스트

목적: 어떤 지표가 HERD 신호 품질에 실제로 기여하는지 검증.
      구성 A(현재 v2 기준선) 대비 B/C/D의 수익률·MDD·신호 수 변화 관찰.

구성 A: v2 기준선 (6개 지표)
구성 B: 월봉 RSI 제거
구성 C: MA200 이격도 제거 (200주 MA와 중복 가능성)
구성 D: 월봉 RSI + MA200 이격도 둘 다 제거

전략: 트레일링 스탑 (EPS 필터 없음 — 순수 지표 구성 비교용)
  Rush(≥75)  → 트레일링 스탑 설정 (고점 -8%, 60거래일, 30% 매도)
  Drift(60~75) → 즉시 5% 익절
  Flee(≤15)  → 즉시 30% 추가매수
  쿨다운: 20거래일

최적화: 6개 지표 시계열을 종목당 1회 계산 후 구성별 가중치만 다르게 적용
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
# 비교할 4가지 지표 구성
# ══════════════════════════════════════════════
# 키 이름은 _INDICATOR_FUNCS와 동일하게 맞춤 (매핑 없이 직접 적용)
CONFIGS: dict[str, dict[str, float]] = {
    "A (v2 기준선)": {
        "monthly_rsi":     0.20,
        "weekly_rsi":      0.18,
        "position_52w":    0.18,
        "ma200_deviation": 0.14,
        "volume_strength": 0.10,
        "ma200_weekly":    0.20,
    },
    "B (월봉RSI 제거)": {
        "weekly_rsi":      0.28,
        "position_52w":    0.22,
        "ma200_deviation": 0.15,
        "volume_strength": 0.15,
        "ma200_weekly":    0.20,
    },
    "C (MA200이격 제거)": {
        "monthly_rsi":     0.23,
        "weekly_rsi":      0.22,
        "position_52w":    0.22,
        "volume_strength": 0.13,
        "ma200_weekly":    0.20,
    },
    "D (월봉+이격 제거)": {
        "weekly_rsi":      0.35,
        "position_52w":    0.25,
        "volume_strength": 0.20,
        "ma200_weekly":    0.20,
    },
}

# 가중치 합계 검증
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
}


# ──────────────────────────────────────────────
# 전략 파라미터
# ──────────────────────────────────────────────
INITIAL_CASH      = 10_000.0
FEE_RATE          = 0.001

RUSH_THRESHOLD    = 75.0
DRIFT_LOWER       = 60.0
FLEE_THRESHOLD    = 15.0
SIGNAL_COOLDOWN   = 20

DRIFT_SELL_RATIO  = 0.05
FLEE_BUY_RATIO    = 0.30
TRAILING_STOP_PCT = 0.08
TRAILING_MAX_DAYS = 60
TRAILING_SELL_RATIO = 0.30

TICKERS     = ["NVDA", "MSFT", "KO", "JPM", "SPY"]
DATA_PERIOD = "10y"
MIN_ROWS    = 252 + 21  # MA200 계산에 필요한 최소 행 수 + 여유분


# ══════════════════════════════════════════════
# 지표 시계열 사전 계산 (종목당 1회 — 4개 구성 공통)
# ══════════════════════════════════════════════
def _build_all_indicator_series(df: pd.DataFrame) -> dict[str, pd.Series]:
    """
    6개 지표 전부를 시계열로 계산해 반환한다.
    한 번만 계산하면 4가지 구성 모두 가중치만 다르게 적용 가능.

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
    weights에 없는 지표는 자동으로 제외된다 (가중치 = 0).
    """
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
class ConfigResult:
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
# 전략 C — 트레일링 스탑 (EPS 필터 없음)
# ══════════════════════════════════════════════
def _run_trailing_stop(
    close: pd.Series,
    herd: pd.Series,
    ticker: str,
    config_name: str,
) -> ConfigResult:
    """
    순수 지표 비교용 트레일링 스탑 전략.
    EPS 서프라이즈 필터 없이 Rush 발생 시 모두 트레일링 스탑으로 처리.
    """
    result = ConfigResult(ticker=ticker, config_name=config_name)
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


def run_config_backtest() -> None:
    print()
    print("═" * 95)
    print("  지표 구성별 성능 비교 백테스트")
    print(f"  종목: {', '.join(TICKERS)}  |  기간: {DATA_PERIOD}")
    print(f"  전략: 트레일링 스탑  Rush≥{RUSH_THRESHOLD:.0f} / Flee≤{FLEE_THRESHOLD:.0f}")
    print(f"  트레일링 스탑: 고점 -{TRAILING_STOP_PCT*100:.0f}% / 최대 {TRAILING_MAX_DAYS}거래일")
    print("═" * 95)

    # config_name → 종목별 결과 리스트 (tickers 순서 유지)
    all_results: dict[str, list[ConfigResult]] = {name: [] for name in CONFIGS}

    for ticker in TICKERS:
        print(f"\n  [{ticker}] 데이터 수집 + 지표 시계열 계산 중...", end=" ", flush=True)
        df = collect(ticker, period=DATA_PERIOD)
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date").sort_index()
        close = df["Close"]

        # 6개 지표 시계열을 1회만 계산 (4개 구성 공통)
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

    # ── 구성별 요약 테이블 ─────────────────────────────────────────────────
    print()
    print("═" * 95)
    print("  === 구성별 평균 비교 요약 ===")
    print("═" * 95)
    header = (
        f"  {'구성':<22}  {'평균 수익률':>10}  {'vs A':>7}  "
        f"{'평균 MDD':>9}  {'vs A':>7}  {'Rush 합계':>9}  {'Flee 합계':>9}"
    )
    print(header)
    print("  " + "─" * 90)

    # A 구성 기준값 먼저 계산
    a_results = all_results["A (v2 기준선)"]
    a_avg_ret = sum(r.return_pct() for r in a_results) / n
    a_avg_mdd = sum(r.mdd() for r in a_results) / n

    for config_name, results in all_results.items():
        avg_ret    = sum(r.return_pct() for r in results) / n
        avg_mdd    = sum(r.mdd() for r in results) / n
        total_rush = sum(r.rush_signals for r in results)
        total_flee = sum(r.flee_signals for r in results)
        vs_ret     = avg_ret - a_avg_ret
        vs_mdd     = avg_mdd - a_avg_mdd  # 음수 = MDD 개선 (낙폭 줄었음)

        is_baseline = config_name.startswith("A")
        vs_ret_str = "  (기준)" if is_baseline else _fmt(vs_ret)
        vs_mdd_str = "  (기준)" if is_baseline else _fmt(vs_mdd)

        print(
            f"  {config_name:<22}  {_fmt(avg_ret):>10}  {vs_ret_str:>7}  "
            f"{avg_mdd:>8.1f}%  {vs_mdd_str:>7}  "
            f"{total_rush:>8}회  {total_flee:>8}회"
        )

    print()
    print("  ※ vs A 해석:")
    print("    수익률 vs A > 0   → 해당 지표를 제거해도 수익 개선 (지표 기여 의심)")
    print("    수익률 vs A < 0   → 해당 지표 제거 시 수익 감소 (지표 실제 기여)")
    print("    MDD     vs A < 0  → MDD 개선 (낙폭 감소)  |  > 0 → MDD 악화")

    # ── 종목별 상세 테이블 ────────────────────────────────────────────────
    print()
    print("═" * 95)
    print("  === 종목별 수익률 상세 ===")
    print("═" * 95)
    short_names = [name.split(" ")[0] for name in CONFIGS.keys()]  # A, B, C, D
    print(
        f"  {'종목':<6}  "
        + "  ".join(f"{'['+s+']수익':>8}  {'['+s+']MDD':>7}" for s in short_names)
    )
    print("  " + "─" * 90)

    config_result_lists = list(all_results.values())
    for i, ticker in enumerate(TICKERS):
        row = f"  {ticker:<6}  "
        row += "  ".join(
            f"{_fmt(results[i].return_pct()):>8}  {results[i].mdd():>6.1f}%"
            for results in config_result_lists
        )
        print(row)

    # ── Rush / Flee 신호 수 상세 ──────────────────────────────────────────
    print()
    print("═" * 95)
    print("  === 종목별 Rush / Flee 신호 수 ===")
    print("═" * 95)
    print(
        f"  {'종목':<6}  "
        + "  ".join(f"{'['+s+']Rush':>7} {'['+s+']Flee':>7}" for s in short_names)
    )
    print("  " + "─" * 90)

    for i, ticker in enumerate(TICKERS):
        row = f"  {ticker:<6}  "
        row += "  ".join(
            f"{results[i].rush_signals:>5}회  {results[i].flee_signals:>5}회"
            for results in config_result_lists
        )
        print(row)

    print()


if __name__ == "__main__":
    run_config_backtest()
