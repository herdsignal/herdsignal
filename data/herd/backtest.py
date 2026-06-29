"""
herd/backtest.py — HERD Index 신호 백테스트
5년 일봉 데이터 전체에서 매일 HERD Index를 산출한 뒤,
Rush(≥80) / Flee(≤20) 신호가 발생했을 때 이후 수익률을 검증한다.
"""

import logging
from dataclasses import dataclass, field

import pandas as pd

from collectors.stock_collector import collect
from indicators.rsi import calc_weekly_rsi, calc_monthly_rsi
from indicators.price_position import calc_52w_position, calc_ma200_deviation
from indicators.volume import calc_volume_strength
from indicators.ma200_weekly import calc_ma200_weekly
from herd.calculator import calc_herd_score, get_stage, IndicatorValues

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 백테스트 설정 상수
# ──────────────────────────────────────────────
RUSH_THRESHOLD  = 80.0   # Rush 신호 기준값 (이 이상)
FLEE_THRESHOLD  = 20.0   # Flee 신호 기준값 (이 이하)
SIGNAL_COOLDOWN = 10     # 연속 신호 중복 제거 쿨다운 (거래일 수)

# 수익률 측정 시점 (거래일 기준)
FORWARD_WINDOWS = {
    "1개월":  21,
    "3개월":  63,
    "6개월":  126,
    "12개월": 252,
}


# ──────────────────────────────────────────────
# 결과 자료구조
# ──────────────────────────────────────────────
@dataclass
class SignalRecord:
    """신호 발생 시점의 데이터와 이후 수익률을 담는 레코드."""
    date:          pd.Timestamp
    score:         float
    close_at_signal: float
    # 이후 수익률 (키: "1개월" 등, 값: %, 데이터 없으면 None)
    forward_returns: dict = field(default_factory=dict)


@dataclass
class ScenarioResult:
    """시나리오(Rush/Flee) 하나의 백테스트 집계 결과."""
    signal_type:   str               # "Rush" or "Flee"
    records:       list[SignalRecord] = field(default_factory=list)

    def count(self) -> int:
        return len(self.records)

    def avg_return(self, window: str) -> float | None:
        """해당 기간 수익률의 평균. 데이터 없으면 None."""
        vals = [r.forward_returns[window]
                for r in self.records
                if r.forward_returns.get(window) is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    def accuracy(self) -> float | None:
        """
        신호 정확도:
        - Rush: 이후 12개월 하락한 비율
        - Flee: 이후 12개월 상승한 비율
        """
        vals = [r.forward_returns["12개월"]
                for r in self.records
                if r.forward_returns.get("12개월") is not None]
        if not vals:
            return None
        if self.signal_type == "Rush":
            correct = sum(1 for v in vals if v < 0)
        else:
            correct = sum(1 for v in vals if v > 0)
        return round(correct / len(vals) * 100, 1)


# ──────────────────────────────────────────────
# HERD Index 시계열 산출
# ──────────────────────────────────────────────
def _build_herd_series(df: pd.DataFrame) -> pd.Series:
    """
    일봉 DataFrame의 각 날짜에 대해 HERD Index를 산출한다.
    충분한 데이터가 쌓인 시점(252 거래일 이후)부터 계산 시작.
    계산 불가 날짜는 NaN으로 채운다.
    """
    # 지표 계산에 필요한 최소 데이터 (MA200 기준)
    MIN_ROWS = 252 + 21   # MA200 + 여유분

    scores = {}

    for i in range(MIN_ROWS, len(df)):
        # 해당 시점까지의 슬라이스만 전달 (미래 데이터 유출 방지)
        slice_df = df.iloc[:i + 1].copy()
        date = df.index[i] if isinstance(df.index, pd.DatetimeIndex) else pd.Timestamp(df["Date"].iloc[i])

        try:
            indicators = IndicatorValues(
                weekly_rsi      = calc_weekly_rsi(slice_df),
                monthly_rsi     = calc_monthly_rsi(slice_df),
                position_52w    = calc_52w_position(slice_df),
                ma200_deviation = calc_ma200_deviation(slice_df),
                volume_strength = calc_volume_strength(slice_df),
                ma200_weekly    = calc_ma200_weekly(slice_df),
            )
            scores[date] = calc_herd_score(indicators)
        except Exception as e:
            logger.debug(f"  {date} 계산 스킵: {e}")
            scores[date] = float("nan")

    return pd.Series(scores, name="herd_score")


def _extract_signals(herd_series: pd.Series,
                     threshold: float,
                     direction: str) -> list[pd.Timestamp]:
    """
    HERD 시계열에서 신호 날짜를 추출한다.
    연속된 신호는 SIGNAL_COOLDOWN 거래일 이내 재발생을 무시한다.

    Args:
        direction: "above" (Rush) 또는 "below" (Flee)
    """
    if direction == "above":
        signal_mask = herd_series >= threshold
    else:
        signal_mask = herd_series <= threshold

    signal_dates = herd_series[signal_mask].index.tolist()

    # 쿨다운 적용 — 직전 신호로부터 SIGNAL_COOLDOWN 거래일 이내면 제외
    deduplicated = []
    last_signal_pos = -SIGNAL_COOLDOWN - 1
    all_dates = herd_series.index.tolist()

    for date in signal_dates:
        pos = all_dates.index(date)
        if pos - last_signal_pos > SIGNAL_COOLDOWN:
            deduplicated.append(date)
            last_signal_pos = pos

    return deduplicated


def _calc_forward_returns(close_series: pd.Series,
                           signal_date: pd.Timestamp,
                           signal_close: float) -> dict:
    """
    신호 발생 시점 종가 대비 이후 각 기간의 수익률을 계산한다.
    데이터가 부족한 기간은 None으로 처리한다.
    """
    all_dates = close_series.index.tolist()
    try:
        base_pos = all_dates.index(signal_date)
    except ValueError:
        return {}

    returns = {}
    for label, days in FORWARD_WINDOWS.items():
        target_pos = base_pos + days
        if target_pos >= len(all_dates):
            returns[label] = None   # 미래 데이터 없음
            continue
        target_close = float(close_series.iloc[target_pos])
        returns[label] = round((target_close - signal_close) / signal_close * 100, 2)

    return returns


# ──────────────────────────────────────────────
# 종목 단위 백테스트 실행
# ──────────────────────────────────────────────
def run_backtest(ticker: str) -> tuple[ScenarioResult, ScenarioResult]:
    """
    단일 종목의 5년 데이터로 Rush / Flee 시나리오 백테스트를 실행한다.

    Returns:
        (rush_result, flee_result)
    """
    logger.info(f"[{ticker}] 백테스트 시작")

    # 데이터 수집 및 날짜 인덱스 정렬
    df = collect(ticker)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()

    close_series = df["Close"]

    # HERD Index 시계열 산출 (시간이 오래 걸림)
    logger.info(f"[{ticker}] HERD 시계열 산출 중... (약 {len(df)}일)")
    herd_series = _build_herd_series(df)

    # Rush / Flee 신호 날짜 추출
    rush_dates = _extract_signals(herd_series, RUSH_THRESHOLD, "above")
    flee_dates = _extract_signals(herd_series, FLEE_THRESHOLD, "below")

    # 각 신호별 수익률 계산
    rush_result = ScenarioResult(signal_type="Rush")
    for date in rush_dates:
        close_price = float(close_series.loc[date])
        fwd = _calc_forward_returns(close_series, date, close_price)
        rush_result.records.append(SignalRecord(
            date             = date,
            score            = float(herd_series.loc[date]),
            close_at_signal  = close_price,
            forward_returns  = fwd,
        ))

    flee_result = ScenarioResult(signal_type="Flee")
    for date in flee_dates:
        close_price = float(close_series.loc[date])
        fwd = _calc_forward_returns(close_series, date, close_price)
        flee_result.records.append(SignalRecord(
            date             = date,
            score            = float(herd_series.loc[date]),
            close_at_signal  = close_price,
            forward_returns  = fwd,
        ))

    logger.info(
        f"[{ticker}] 완료 — Rush 신호 {rush_result.count()}회, "
        f"Flee 신호 {flee_result.count()}회"
    )
    return rush_result, flee_result


# ──────────────────────────────────────────────
# 결과 출력
# ──────────────────────────────────────────────
def _fmt_pct(value: float | None) -> str:
    """수익률 포맷: None이면 '데이터 부족'으로 표시."""
    if value is None:
        return "  데이터 부족"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}%"


def print_result(ticker: str,
                 rush: ScenarioResult,
                 flee: ScenarioResult) -> None:
    """백테스트 결과를 지정 형식으로 출력한다."""
    sep = "=" * 46

    print()
    print(sep)
    print(f"  {ticker} 백테스트 결과")
    print(sep)

    # Rush 시나리오
    print()
    print("  [Herd Rush 신호 — 익절 타이밍]")
    print(f"  신호 발생 횟수: {rush.count()}회")
    if rush.count() > 0:
        print("  신호 이후 평균 수익률:")
        for label in FORWARD_WINDOWS:
            avg = rush.avg_return(label)
            print(f"    {label} 후: {_fmt_pct(avg)}"
                  + ("  (양수=신호 틀림, 음수=신호 맞음)" if label == "1개월" else ""))
        acc = rush.accuracy()
        print(f"  신호 정확도 (이후 하락한 비율): "
              f"{'데이터 부족' if acc is None else f'{acc}%'}")
    else:
        print("  → 신호 없음")

    # Flee 시나리오
    print()
    print("  [Herd Flee 신호 — 매수 타이밍]")
    print(f"  신호 발생 횟수: {flee.count()}회")
    if flee.count() > 0:
        print("  신호 이후 평균 수익률:")
        for label in FORWARD_WINDOWS:
            avg = flee.avg_return(label)
            print(f"    {label} 후: {_fmt_pct(avg)}"
                  + ("  (양수=신호 맞음, 음수=신호 틀림)" if label == "1개월" else ""))
        acc = flee.accuracy()
        print(f"  신호 정확도 (이후 상승한 비율): "
              f"{'데이터 부족' if acc is None else f'{acc}%'}")
    else:
        print("  → 신호 없음")

    print()
