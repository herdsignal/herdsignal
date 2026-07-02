"""
backfill_spy.py — SPY HERD 점수 3년치 역사적 백필

날짜별로 DataFrame을 슬라이스해 지표를 계산하고
herd_scores + herd_indicators 테이블에 UPSERT한다.

실행: python data/backfill_spy.py
"""

import logging
import sys
from datetime import date
from pathlib import Path

import pandas as pd

# data/ 디렉터리를 sys.path에 추가 (패키지 import 기준점)
_DATA_DIR = Path(__file__).resolve().parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from collectors.stock_collector import collect
from config.settings import YFINANCE_PERIOD
from herd.calculator import IndicatorValues, calc_herd_score, get_stage
from herd.saver import save_herd_for_date
from indicators.ma200_weekly import calc_ma200_weekly
from indicators.price_position import calc_52w_position, calc_ma200_deviation
from indicators.rsi import calc_monthly_rsi, calc_weekly_rsi
from indicators.volume import calc_volume_strength

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 백필 설정
# ──────────────────────────────────────────────
TICKER         = "SPY"
BACKFILL_YEARS = 3   # 백필 기간 (년)

# 백분위수 정규화 품질 확보를 위해 YFINANCE_PERIOD(5y) + 백필 기간(3y) 만큼 수집.
# 3y만 수집하면 가장 오래된 날짜에서 컨텍스트 부족으로 지표 신뢰도가 낮아짐.
_context_years = int(YFINANCE_PERIOD.replace("y", ""))
COLLECT_PERIOD = f"{_context_years + BACKFILL_YEARS}y"


# ──────────────────────────────────────────────
# 지표 계산
# ──────────────────────────────────────────────
def _calc_indicators(df_slice: pd.DataFrame) -> IndicatorValues | None:
    """
    슬라이스된 DataFrame으로 6개 지표를 계산한다.
    calculator.py와 동일한 함수를 그대로 재사용.
    하나라도 실패하면 None을 반환한다.
    """
    funcs = {
        "weekly_rsi":      lambda: calc_weekly_rsi(df_slice),
        "monthly_rsi":     lambda: calc_monthly_rsi(df_slice),
        "position_52w":    lambda: calc_52w_position(df_slice),
        "ma200_deviation": lambda: calc_ma200_deviation(df_slice),
        "volume_strength": lambda: calc_volume_strength(df_slice),
        "ma200_weekly":    lambda: calc_ma200_weekly(df_slice),
    }

    values: dict[str, float] = {}
    for name, func in funcs.items():
        try:
            values[name] = func()
        except Exception as e:
            logger.warning(f"[{TICKER}] 지표 계산 실패 — {name}: {e}")
            return None

    return IndicatorValues(
        weekly_rsi      = values["weekly_rsi"],
        monthly_rsi     = values["monthly_rsi"],
        position_52w    = values["position_52w"],
        ma200_deviation = values["ma200_deviation"],
        volume_strength = values["volume_strength"],
        ma200_weekly    = values["ma200_weekly"],
    )


# ──────────────────────────────────────────────
# 메인 백필 실행
# ──────────────────────────────────────────────
def run_backfill() -> None:
    print(f"\n{'='*60}")
    print(f"  SPY HERD 백필 — 최근 {BACKFILL_YEARS}년")
    print(f"  데이터 수집 기간: {COLLECT_PERIOD}")
    print(f"  저장 테이블: herd_scores + herd_indicators")
    print(f"{'='*60}")

    # 1. 데이터 수집
    print(f"\n[1/3] yfinance SPY {COLLECT_PERIOD} 데이터 수집 중...")
    try:
        df = collect(TICKER, period=COLLECT_PERIOD)
    except Exception as e:
        print(f"  ❌ 데이터 수집 실패: {e}")
        return

    # Date 컬럼 → DatetimeIndex 변환
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")
    df = df.sort_index()
    print(f"  ✓ {len(df)}일 수집 완료  ({df.index[0].date()} ~ {df.index[-1].date()})")

    # 2. 백필 날짜 범위 결정
    today = date.today()
    cutoff = pd.Timestamp(today.replace(year=today.year - BACKFILL_YEARS))
    backfill_dates = [dt for dt in df.index if dt >= cutoff]
    total = len(backfill_dates)

    print(f"\n[2/3] 백필 범위: {cutoff.date()} ~ {df.index[-1].date()}  ({total}개 거래일)")

    if total == 0:
        print("  ❌ 백필 대상 날짜 없음. 데이터 수집 기간을 확인하세요.")
        return

    # 3. 날짜별 루프 (오래된 날짜부터)
    print(f"\n[3/3] 계산 및 저장 시작...\n")

    success = 0
    failure = 0

    for i, dt in enumerate(backfill_dates):
        score_date = dt.date()
        prefix = f"  [{i+1:4d}/{total}] {score_date}"

        # 해당 날짜까지 누적 슬라이스 (지표 정규화에 필요한 과거 데이터 포함)
        df_slice = df.loc[:dt]

        # 6개 지표 계산
        indicators = _calc_indicators(df_slice)
        if indicators is None:
            print(f"{prefix} → ⚠️  지표 계산 실패, SKIP")
            failure += 1
            continue

        score = calc_herd_score(indicators)
        stage = get_stage(score)

        herd_result = {
            "ticker":     TICKER,
            "score":      score,
            "stage":      stage,
            "indicators": indicators,
        }

        # DB 저장 (UPSERT — 이미 존재하면 UPDATE)
        ok = save_herd_for_date(TICKER, herd_result, score_date)
        if ok:
            print(f"{prefix} → {score:5.2f}  {stage}")
            success += 1
        else:
            print(f"{prefix} → ❌ 저장 실패, SKIP")
            failure += 1

    # 4. 완료 요약
    print(f"\n{'='*60}")
    print(f"  백필 완료 — 성공 {success}건 / 실패 {failure}건 / 전체 {total}건")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    run_backfill()
