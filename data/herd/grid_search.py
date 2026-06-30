"""
herd/grid_search.py — HERD 가중치 그리드 서치 (과적합 방지 버전)

데이터 분할 전략:
  - 훈련 기간 (앞 7년): 최적 가중치 탐색
  - 검증 기간 (뒤 3년): 훈련 결과의 과적합 여부 검증

그리드 서치 범위 (volume_strength 고정 0%):
  monthly_rsi, ma200_weekly   : 20~30% (선행성 분석에서 핵심 지표)
  weekly_rsi, position_52w, ma200_deviation : 10~25%
  → 합계 100%인 조합만 유효 (96개)

과적합 판단 기준:
  훈련 TOP10이 검증에서도 TOP20 이내이면 안정적,
  순위가 크게 급락하면 과적합 의심.
"""

import itertools
import logging
import sys
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.WARNING)

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from collectors.stock_collector import collect                # noqa: E402
from indicators.rsi import calc_weekly_rsi, calc_monthly_rsi # noqa: E402
from indicators.price_position import (                      # noqa: E402
    calc_52w_position,
    calc_ma200_deviation,
)
from indicators.ma200_weekly import calc_ma200_weekly        # noqa: E402


# ══════════════════════════════════════════════
# 설정 상수
# ══════════════════════════════════════════════
TICKERS     = ["NVDA", "MSFT", "KO", "JPM", "SPY"]
DATA_PERIOD = "10y"
TRAIN_YEARS = 7   # 훈련 기간 (년)
TEST_YEARS  = 3   # 검증 기간 (년)
MIN_ROWS    = 252 + 21  # 지표 계산 최소 일봉 수

# 트레일링 스탑 전략 파라미터
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

# 현재 v3 가중치 — 그리드에 없는 값(24%, 19% 등)이므로 별도 평가
V3_WEIGHTS = {
    "monthly_rsi":     0.24,
    "weekly_rsi":      0.19,
    "position_52w":    0.19,
    "ma200_deviation": 0.18,
    "volume_strength": 0.00,  # 비활성화
    "ma200_weekly":    0.20,
}

# 그리드 서치 후보 범위 (단위: %, 5% 단위)
_GRID = {
    "monthly_rsi":     [20, 25, 30],      # 장기 모멘텀 — 선행성 가장 강함
    "ma200_weekly":    [20, 25, 30],      # 장기 구조적 저점/고점
    "weekly_rsi":      [10, 15, 20, 25],  # 중기 모멘텀
    "position_52w":    [10, 15, 20, 25],  # 연간 가격 위치
    "ma200_deviation": [10, 15, 20, 25],  # 중기 추세 이탈
}

# 지표 계산 함수 (volume_strength 제외 — 항상 0이므로 연산 생략)
_INDICATOR_FUNCS = {
    "monthly_rsi":     calc_monthly_rsi,
    "weekly_rsi":      calc_weekly_rsi,
    "position_52w":    calc_52w_position,
    "ma200_deviation": calc_ma200_deviation,
    "ma200_weekly":    calc_ma200_weekly,
}


# ══════════════════════════════════════════════
# 유효 조합 열거
# ══════════════════════════════════════════════
def _enumerate_combos() -> list[dict]:
    """합계 정확히 100%인 가중치 조합을 모두 열거한다."""
    combos = []
    for mr, mw, wr, p52, m2d in itertools.product(
        _GRID["monthly_rsi"],
        _GRID["ma200_weekly"],
        _GRID["weekly_rsi"],
        _GRID["position_52w"],
        _GRID["ma200_deviation"],
    ):
        if mr + mw + wr + p52 + m2d == 100:
            combos.append({
                "monthly_rsi":     mr  / 100,
                "weekly_rsi":      wr  / 100,
                "position_52w":    p52 / 100,
                "ma200_deviation": m2d / 100,
                "volume_strength": 0.00,
                "ma200_weekly":    mw  / 100,
            })
    return combos


def _label(w: dict) -> str:
    """가중치 조합을 '월/주/52주/이격/200주' 형식으로 축약 표현한다."""
    return (
        f"{int(w['monthly_rsi']*100):2d}/"
        f"{int(w['weekly_rsi']*100):2d}/"
        f"{int(w['position_52w']*100):2d}/"
        f"{int(w['ma200_deviation']*100):2d}/"
        f"{int(w['ma200_weekly']*100):2d}"
    )


# ══════════════════════════════════════════════
# 지표 시계열 계산 (종목당 1회 — 모든 조합 공통)
# ══════════════════════════════════════════════
def _build_indicator_series(df: pd.DataFrame) -> dict[str, pd.Series]:
    """
    5개 지표 시계열을 종목당 1회 계산한다.
    look-ahead bias 방지: i번째 날까지의 슬라이스만 각 함수에 전달.
    """
    raw = {key: {} for key in _INDICATOR_FUNCS}
    total = len(df)
    for i in range(MIN_ROWS, total):
        slice_df = df.iloc[:i + 1].copy()
        date = df.index[i]
        for key, func in _INDICATOR_FUNCS.items():
            try:
                raw[key][date] = func(slice_df)
            except Exception:
                raw[key][date] = float("nan")
    return {k: pd.Series(v, name=k) for k, v in raw.items()}


def _apply_weights(
    indicators: dict[str, pd.Series],
    weights: dict[str, float],
) -> pd.Series:
    """사전 계산된 지표에 가중치를 적용해 HERD 시계열을 반환한다."""
    herd = None
    for key, w in weights.items():
        if w == 0.0 or key not in indicators:
            continue
        series = indicators[key] * w
        herd = series if herd is None else herd + series
    return herd.clip(0, 100).round(2)  # type: ignore[union-attr]


# ══════════════════════════════════════════════
# 트레일링 스탑 전략 (단일 기간 독립 평가)
# ══════════════════════════════════════════════
def _buy(c: float, s: float, p: float, r: float) -> tuple[float, float]:
    spend = c * r
    return c - spend, s + (spend / (1 + FEE_RATE)) / p


def _sell(c: float, s: float, p: float, r: float) -> tuple[float, float]:
    out = s * r
    return c + out * p * (1 - FEE_RATE), s - out


def _run_period(close: pd.Series, herd: pd.Series) -> tuple[float, float]:
    """
    지정 기간(close·herd 슬라이스)에서 트레일링 스탑 전략을 독립 실행한다.
    훈련/검증 기간 각각 첫날 전액 매수로 초기화해 독립적으로 비교한다.
    반환: (수익률 %, MDD %)
    """
    if len(close) < 10:
        return 0.0, 0.0

    cash, shares = _buy(INITIAL_CASH, 0.0, float(close.iloc[0]), 1.0)
    last_sell = -SIGNAL_COOLDOWN - 1
    last_buy  = -SIGNAL_COOLDOWN - 1
    trailing_active    = False
    trailing_high      = 0.0
    trailing_days_left = 0
    portfolio_values: list[float] = []

    for i, (date, price) in enumerate(close.items()):
        price = float(price)
        score = float(herd.get(date, float("nan")))

        # 트레일링 스탑 상태 업데이트
        if trailing_active:
            if price > trailing_high:
                trailing_high = price
            trailing_days_left -= 1
            if price <= trailing_high * (1 - TRAILING_STOP_PCT):
                cash, shares = _sell(cash, shares, price, TRAILING_SELL_RATIO)
                last_sell = i
                trailing_active = False
            elif trailing_days_left <= 0:
                trailing_active = False

        # HERD 신호 처리
        if pd.notna(score):
            sell_ok = (i - last_sell) > SIGNAL_COOLDOWN
            buy_ok  = (i - last_buy)  > SIGNAL_COOLDOWN

            if score >= RUSH_THRESHOLD and shares > 0 and sell_ok and not trailing_active:
                trailing_active    = True
                trailing_high      = price
                trailing_days_left = TRAILING_MAX_DAYS
                last_sell = i
            elif DRIFT_LOWER <= score < RUSH_THRESHOLD and shares > 0 and sell_ok:
                cash, shares = _sell(cash, shares, price, DRIFT_SELL_RATIO)
                last_sell = i
            elif score <= FLEE_THRESHOLD and cash > 1.0 and buy_ok:
                cash, shares = _buy(cash, shares, price, FLEE_BUY_RATIO)
                last_buy = i

        portfolio_values.append(cash + shares * price)

    if not portfolio_values:
        return 0.0, 0.0

    # 수익률 계산
    ret = (portfolio_values[-1] / INITIAL_CASH - 1) * 100

    # MDD 계산
    peak = INITIAL_CASH
    max_dd = 0.0
    for v in portfolio_values:
        if v > peak:
            peak = v
        dd = (v - peak) / peak * 100
        if dd < max_dd:
            max_dd = dd

    return ret, max_dd


# ══════════════════════════════════════════════
# 단일 종목 × 단일 조합의 훈련·검증 수익률 계산
# ══════════════════════════════════════════════
def _eval_combo(
    weights: dict,
    ticker_data: dict[str, tuple],
) -> tuple[float, float, float, float]:
    """
    5개 종목 평균 수익률을 훈련/검증 기간 각각 계산한다.
    반환: (train_ret, train_mdd, test_ret, test_mdd)
    """
    n = len(TICKERS)
    train_rets, train_mdds = [], []
    test_rets,  test_mdds  = [], []

    for ticker in TICKERS:
        close, indicators, split_date = ticker_data[ticker]
        herd = _apply_weights(indicators, weights)

        # 훈련 기간
        tr_close = close[close.index <= split_date]
        tr_herd  = herd[herd.index   <= split_date]
        ret, mdd = _run_period(tr_close, tr_herd)
        train_rets.append(ret);  train_mdds.append(mdd)

        # 검증 기간
        te_close = close[close.index > split_date]
        te_herd  = herd[herd.index   > split_date]
        ret, mdd = _run_period(te_close, te_herd)
        test_rets.append(ret);   test_mdds.append(mdd)

    return (
        sum(train_rets) / n,
        sum(train_mdds) / n,
        sum(test_rets)  / n,
        sum(test_mdds)  / n,
    )


# ══════════════════════════════════════════════
# 메인 — 그리드 서치 실행 및 결과 출력
# ══════════════════════════════════════════════
def run_grid_search() -> None:
    combos = _enumerate_combos()
    n_combos = len(combos)

    print()
    print("═" * 100)
    print("  HERD 가중치 그리드 서치 (과적합 방지)")
    print(f"  종목: {', '.join(TICKERS)}  |  기간: {DATA_PERIOD}")
    print(f"  훈련: 앞 {TRAIN_YEARS}년  /  검증: 뒤 {TEST_YEARS}년  |  유효 조합: {n_combos}개")
    print(f"  가중치 표기: 월봉RSI / 주봉RSI / 52주위치 / MA200이격 / MA200주간")
    print("═" * 100)

    # ── 1단계: 데이터 수집 + 지표 시계열 계산 ─────────────────────────────
    ticker_data: dict[str, tuple] = {}

    for ticker in TICKERS:
        print(f"\n  [{ticker}] 데이터 수집 + 지표 시계열 계산 중...", end=" ", flush=True)
        df = collect(ticker, period=DATA_PERIOD)
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date").sort_index()
        close = df["Close"]

        # 검증 기간 = 마지막 3년, 훈련 기간 = 그 이전
        split_date = close.index[-1] - pd.DateOffset(years=TEST_YEARS)
        train_n = int((close.index <= split_date).sum())
        test_n  = int((close.index >  split_date).sum())

        indicators = _build_indicator_series(df)
        print(
            f"{len(df)}일 완료  "
            f"(훈련 {train_n}일 / 검증 {test_n}일 "
            f"| 분할일: {split_date.date()})"
        )
        ticker_data[ticker] = (close, indicators, split_date)

    # ── 2단계: 모든 조합 훈련·검증 동시 평가 ──────────────────────────────
    print(f"\n  [평가] {n_combos}개 조합 × {len(TICKERS)}종목 백테스트 중...")

    all_results: list[dict] = []

    for idx, weights in enumerate(combos, 1):
        if idx % 10 == 0 or idx == n_combos:
            print(f"    [{idx:3d}/{n_combos}] 진행 중...", end="\r", flush=True)

        tr_ret, tr_mdd, te_ret, te_mdd = _eval_combo(weights, ticker_data)
        all_results.append({
            "weights":   weights,
            "train_ret": tr_ret,
            "train_mdd": tr_mdd,
            "test_ret":  te_ret,
            "test_mdd":  te_mdd,
        })

    print()

    # v3 가중치도 별도 평가 (그리드에 없는 값이므로 독립 실행)
    v3_tr_ret, v3_tr_mdd, v3_te_ret, v3_te_mdd = _eval_combo(V3_WEIGHTS, ticker_data)

    # ── 3단계: 훈련·검증 각각 순위 부여 ──────────────────────────────────
    # 훈련 순위
    train_sorted = sorted(all_results, key=lambda x: x["train_ret"], reverse=True)
    for rank, r in enumerate(train_sorted, 1):
        r["train_rank"] = rank

    # 검증 순위
    test_sorted = sorted(all_results, key=lambda x: x["test_ret"], reverse=True)
    for rank, r in enumerate(test_sorted, 1):
        r["test_rank"] = rank

    # v3 순위 (그리드 결과 기준 상대적 위치)
    v3_train_rank = sum(1 for r in all_results if r["train_ret"] > v3_tr_ret) + 1
    v3_test_rank  = sum(1 for r in all_results if r["test_ret"]  > v3_te_ret) + 1

    # ── 4단계: 훈련 TOP 10 출력 ───────────────────────────────────────────
    top10 = train_sorted[:10]
    median_ret = train_sorted[n_combos // 2]["train_ret"]

    print()
    print("═" * 100)
    print(f"  === 훈련 기간 ({TRAIN_YEARS}년) TOP 10 ===")
    print("═" * 100)
    print(
        f"  {'순위':>4}  "
        f"{'가중치 조합':>14}  "
        f"{'평균 수익률':>11}  "
        f"{'평균 MDD':>9}"
    )
    print("  " + "─" * 45)

    for r in top10:
        print(
            f"  {r['train_rank']:>4}위  "
            f"{_label(r['weights']):>14}  "
            f"{r['train_ret']:>+10.1f}%  "
            f"{r['train_mdd']:>8.1f}%"
        )

    print(f"\n  전체 {n_combos}개 중앙값 수익률: {median_ret:+.1f}%")

    # ── 5단계: 검증 기간 재평가 출력 ──────────────────────────────────────
    print()
    print("═" * 100)
    print(f"  === 검증 기간 ({TEST_YEARS}년) 재평가 — 훈련 TOP10 기준 ===")
    print("═" * 100)
    print(
        f"  {'훈련순위':>6}  "
        f"{'가중치 조합':>14}  "
        f"{'검증 수익률':>11}  "
        f"{'검증 MDD':>9}  "
        f"{'검증순위':>7}  "
        f"{'순위 변동':>9}"
    )
    print("  " + "─" * 75)

    for r in top10:
        # 순위 변동: 양수 = 검증에서 올라감, 음수 = 내려감
        rank_change = r["train_rank"] - r["test_rank"]
        arrow = "▲" if rank_change > 0 else ("▼" if rank_change < 0 else "─")
        change_str = f"{arrow} {abs(rank_change):3d}"
        print(
            f"  {r['train_rank']:>6}위  "
            f"{_label(r['weights']):>14}  "
            f"{r['test_ret']:>+10.1f}%  "
            f"{r['test_mdd']:>8.1f}%  "
            f"{r['test_rank']:>6}위  "
            f"{change_str:>9}"
        )

    # 과적합 진단
    stable = sum(1 for r in top10 if r["test_rank"] <= 20)
    print()
    print(f"  과적합 진단: 훈련 TOP10 중 검증 TOP20 이내 유지 = {stable}/10개")
    if stable >= 7:
        print("  → 과적합 낮음: 훈련 결과가 새로운 기간에도 안정적")
    elif stable >= 4:
        print("  → 과적합 중간: 훈련 최상위 조합 채택 시 주의 필요")
    else:
        print("  → 과적합 높음: 훈련 1위 가중치를 그대로 채택하지 말 것")

    # ── 6단계: 검증 TOP 5 별도 출력 ──────────────────────────────────────
    print()
    print("═" * 100)
    print(f"  === 검증 기간 ({TEST_YEARS}년) 상위 5개 (과적합 없이 검증 우수 조합) ===")
    print("═" * 100)
    print(
        f"  {'검증순위':>6}  "
        f"{'가중치 조합':>14}  "
        f"{'검증 수익률':>11}  "
        f"{'검증 MDD':>9}  "
        f"{'훈련순위':>7}  "
        f"{'훈련 수익률':>11}"
    )
    print("  " + "─" * 75)

    for r in test_sorted[:5]:
        print(
            f"  {r['test_rank']:>6}위  "
            f"{_label(r['weights']):>14}  "
            f"{r['test_ret']:>+10.1f}%  "
            f"{r['test_mdd']:>8.1f}%  "
            f"{r['train_rank']:>6}위  "
            f"{r['train_ret']:>+10.1f}%"
        )

    # ── 7단계: 현재 v3 위치 출력 ──────────────────────────────────────────
    print()
    print("═" * 100)
    print("  === 현재 v3 가중치 위치 ===")
    print("═" * 100)

    v3_lbl = _label(V3_WEIGHTS)
    print(f"  v3 가중치: {v3_lbl}  (※ 5% 그리드 외 조합 — 독립 평가)")
    print()
    print(
        f"  훈련 기간: {v3_tr_ret:>+8.1f}%  MDD {v3_tr_mdd:>5.1f}%  "
        f"→ 그리드 {n_combos}개 기준 {v3_train_rank}위"
    )
    print(
        f"  검증 기간: {v3_te_ret:>+8.1f}%  MDD {v3_te_mdd:>5.1f}%  "
        f"→ 그리드 {n_combos}개 기준 {v3_test_rank}위"
    )

    # 훈련 1위 조합과 v3 비교
    best = top10[0]
    print()
    print("  [훈련 1위 vs 현재 v3 비교]")
    print(
        f"    훈련 1위  {_label(best['weights'])}: "
        f"훈련 {best['train_ret']:+.1f}%  /  검증 {best['test_ret']:+.1f}%"
    )
    print(
        f"    현재 v3   {v3_lbl}       : "
        f"훈련 {v3_tr_ret:+.1f}%  /  검증 {v3_te_ret:+.1f}%"
    )
    print(
        f"    차이              : "
        f"훈련 {best['train_ret'] - v3_tr_ret:+.1f}%p  /  "
        f"검증 {best['test_ret']  - v3_te_ret:+.1f}%p"
    )

    # 최종 권고
    test_gap = best["test_ret"] - v3_te_ret
    print()
    if test_gap > 80:
        print("  권고: 훈련 1위 조합이 검증에서도 v3 대비 유의미하게 우수 → 가중치 업데이트 검토")
    elif test_gap > 0:
        print("  권고: 훈련 1위가 검증에서 소폭 우수하나 차이 미미 → 현재 v3 유지 가능")
    else:
        print("  권고: 검증 기간에서 v3가 훈련 1위보다 우수 → 현재 v3 유지")

    print()


if __name__ == "__main__":
    run_grid_search()
