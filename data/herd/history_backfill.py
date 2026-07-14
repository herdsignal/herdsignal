"""
herd/history_backfill.py — HERD Index 히스토리 백필 스크립트

저장된 HERD 스냅샷이 적은 종목의 차트 표시를 위해 과거 날짜별 HERD 점수를
계산해 herd_scores / herd_indicators에 UPSERT한다.

실행 예시:
    cd data/
    python herd/history_backfill.py --tickers SPY,AAPL --years 3 --freq weekly
    python herd/history_backfill.py --all-tracked --years 3 --freq weekly
    python herd/history_backfill.py --all-stocks --years 3 --freq monthly
    python herd/history_backfill.py --tickers NVDA --years 1 --freq daily --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd

# data/ 하위에서 직접 실행해도 프로젝트 모듈 import가 가능하도록 경로 추가
_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from collectors.stock_collector import collect  # noqa: E402
from config.database import create_db_engine, get_session_factory  # noqa: E402
from config.settings import (  # noqa: E402
    HERD_BACKFILL_FREQ,
    HERD_BACKFILL_SOURCE_PERIOD,
    HERD_BACKFILL_YEARS,
)
from herd.calculator import IndicatorValues, calc_herd_scores, get_stage  # noqa: E402
from herd.history_readiness import is_history_ready  # noqa: E402
from herd.saver import save_herd_for_date  # noqa: E402
from herd.validation_universe import TICKERS as VALIDATION_TICKERS  # noqa: E402
from indicators.ma200_weekly import calc_ma200_weekly  # noqa: E402
from indicators.price_position import calc_52w_position, calc_ma200_deviation  # noqa: E402
from indicators.rsi import calc_monthly_rsi, calc_weekly_rsi  # noqa: E402
from indicators.volume import calc_volume_strength  # noqa: E402
from init_db import HerdScore, Stock, UserPortfolio, UserWatchlist  # noqa: E402

logger = logging.getLogger(__name__)

_engine = create_db_engine()
_SessionFactory = get_session_factory(_engine)

SUPPORTED_FREQS = {"daily", "weekly", "monthly"}


def _normalize_tickers(raw: str | None) -> list[str]:
    """쉼표로 받은 티커 문자열을 대문자 리스트로 변환한다."""
    if not raw:
        return []
    return sorted({t.strip().upper() for t in raw.split(",") if t.strip()})


def _fetch_tracked_tickers(include_stocks: bool = False) -> list[str]:
    """
    서비스 운영 대상 종목을 조회한다.

    범위:
      - user_portfolio 전체
      - user_watchlist 전체
      - SPY 고정
      - include_stocks=True인 경우에만 stocks.is_active = true 포함
    """
    with _SessionFactory() as session:
        stocks: set[str] = set()
        if include_stocks:
            stocks = {
                row.ticker
                for row in session.query(Stock).filter(Stock.is_active.is_(True)).all()
            }
        portfolio = {row.ticker for row in session.query(UserPortfolio).all()}
        watchlist = {row.ticker for row in session.query(UserWatchlist).all()}

    return sorted(stocks | portfolio | watchlist | {"SPY"})


def _existing_score_dates(ticker: str, start_date: date) -> set[date]:
    """이미 저장된 HERD score_date 집합을 반환한다."""
    with _SessionFactory() as session:
        rows = (
            session.query(HerdScore.score_date)
            .filter(HerdScore.ticker == ticker, HerdScore.score_date >= start_date)
            .all()
        )
    return {row[0] for row in rows}


def _prepare_price_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Date 컬럼을 datetime으로 정규화하고 날짜 오름차순으로 정렬한다."""
    out = df.copy()
    out["Date"] = pd.to_datetime(out["Date"])
    return out.sort_values("Date").reset_index(drop=True)


def _candidate_dates(df: pd.DataFrame, start_date: date, freq: str) -> list[pd.Timestamp]:
    """백필할 기준일 후보를 daily/weekly/monthly 단위로 생성한다."""
    if freq not in SUPPORTED_FREQS:
        raise ValueError(f"freq는 {sorted(SUPPORTED_FREQS)} 중 하나여야 합니다: {freq}")

    indexed = df.set_index("Date")
    indexed = indexed[indexed.index.date >= start_date]

    if indexed.empty:
        return []

    if freq == "daily":
        return list(indexed.index)

    rule = "W-FRI" if freq == "weekly" else "ME"
    dates = (
        indexed["Close"]
        .resample(rule)
        .last()
        .dropna()
        .index
    )
    # 진행 중인 주/월의 resample 라벨은 마지막 실제 거래일보다 미래일 수 있다.
    # 완료되지 않은 기간을 확정 히스토리로 저장하지 않는다.
    dates = dates[dates <= indexed.index.max()]

    # 리샘플 bucket 라벨이 실제 휴장일일 수 있어, 각 bucket의 마지막 실제 거래일로 보정한다.
    candidates: list[pd.Timestamp] = []
    for label in dates:
        bucket_start = label - pd.offsets.Week(weekday=0) if freq == "weekly" else label.replace(day=1)
        bucket = indexed[(indexed.index >= bucket_start) & (indexed.index <= label)]
        if not bucket.empty:
            candidates.append(bucket.index[-1])
    return candidates


def _calculate_for_slice(ticker: str, df_slice: pd.DataFrame) -> dict:
    """특정 날짜까지의 가격 데이터로 HERD 기본 점수와 지표값을 계산한다."""
    values = {
        "weekly_rsi": calc_weekly_rsi(df_slice),
        "monthly_rsi": calc_monthly_rsi(df_slice),
        "position_52w": calc_52w_position(df_slice),
        "ma200_deviation": calc_ma200_deviation(df_slice),
        "volume_strength": calc_volume_strength(df_slice),
        "ma200_weekly": calc_ma200_weekly(df_slice),
    }
    indicators = IndicatorValues(
        weekly_rsi=values["weekly_rsi"],
        monthly_rsi=values["monthly_rsi"],
        position_52w=values["position_52w"],
        ma200_deviation=values["ma200_deviation"],
        volume_strength=values["volume_strength"],
        ma200_weekly=values["ma200_weekly"],
    )

    # 과거 시점별 EPS/섹터 승수는 복원하지 않는다. 미래 데이터 누수 방지를 위해 1.0.
    breakdown = calc_herd_scores(
        indicators,
        eps_multiplier=1.0,
        sector_multiplier=1.0,
    )
    score = breakdown["herd_v4"]

    return {
        "ticker": ticker,
        "score": score,
        "stage": get_stage(score),
        "indicators": indicators,
        "herd_base": breakdown["herd_base"],
        "eps_multiplier": 1.0,
        "sector_multiplier": 1.0,
        "herd_v4": score,
    }


def backfill_ticker(
    ticker: str,
    *,
    years: int,
    freq: str,
    source_period: str,
    overwrite: bool,
    dry_run: bool,
) -> tuple[int, int, int]:
    """
    단일 티커의 HERD 히스토리를 백필한다.

    Returns:
        (saved, skipped, failed)
    """
    ticker = ticker.upper().strip()
    start_date = date.today() - timedelta(days=years * 365)
    existing = _existing_score_dates(ticker, start_date)

    logger.info(
        f"[{ticker}] 백필 시작 years={years}, freq={freq}, "
        f"source_period={source_period}, overwrite={overwrite}, dry_run={dry_run}"
    )

    df = _prepare_price_frame(collect(ticker, period=source_period))
    candidates = _candidate_dates(df, start_date, freq)

    saved = skipped = failed = 0
    total = len(candidates)

    for idx, ts in enumerate(candidates, start=1):
        score_date = ts.date()
        if not overwrite and score_date in existing:
            skipped += 1
            continue

        df_slice = df[df["Date"] <= ts].copy()
        if not is_history_ready(df_slice):
            skipped += 1
            continue

        try:
            result = _calculate_for_slice(ticker, df_slice)
            if dry_run:
                saved += 1
                logger.info(
                    f"[{ticker}] DRY {score_date} "
                    f"score={result['score']:.2f} stage={result['stage']}"
                )
            elif save_herd_for_date(ticker, result, score_date):
                saved += 1
            else:
                failed += 1
        except Exception as e:
            # 최소 이력을 충족한 이후의 실패만 실제 계산 오류로 집계한다.
            failed += 1
            logger.warning(f"[{ticker}] {score_date} 백필 실패: {e}")

        if idx % 20 == 0 or idx == total:
            logger.info(
                f"[{ticker}] 진행 {idx}/{total} | 저장 {saved}, "
                f"스킵 {skipped}, 실패 {failed}"
            )

    logger.info(f"[{ticker}] 백필 완료 | 저장 {saved}, 스킵 {skipped}, 실패 {failed}")
    return saved, skipped, failed


def backfill_many(
    tickers: Iterable[str],
    *,
    years: int,
    freq: str,
    source_period: str,
    overwrite: bool,
    dry_run: bool,
) -> dict[str, tuple[int, int, int]]:
    """여러 티커를 순차 백필한다."""
    result: dict[str, tuple[int, int, int]] = {}
    failed_tickers: list[str] = []
    for ticker in tickers:
        try:
            result[ticker] = backfill_ticker(
                ticker,
                years=years,
                freq=freq,
                source_period=source_period,
                overwrite=overwrite,
                dry_run=dry_run,
            )
        except Exception as e:
            failed_tickers.append(ticker)
            logger.warning(f"[{ticker}] 백필 건너뜀: {e}")
            result[ticker] = (0, 0, 1)
    if failed_tickers:
        logger.warning(f"백필 실패 티커 {len(failed_tickers)}개: {failed_tickers}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="HERD Index 히스토리 백필")
    parser.add_argument("--tickers", help="쉼표로 구분한 티커 목록. 예: SPY,AAPL,NVDA")
    parser.add_argument(
        "--all-tracked",
        action="store_true",
        help="포트폴리오 + 관심종목 + SPY 백필",
    )
    parser.add_argument(
        "--all-stocks",
        action="store_true",
        help="stocks 활성 종목까지 포함해 전체 백필. 오래 걸릴 수 있음",
    )
    parser.add_argument(
        "--validation-universe",
        action="store_true",
        help="v6.1 섹터 분산 55종목 유니버스 백필",
    )
    parser.add_argument("--years", type=int, default=HERD_BACKFILL_YEARS)
    parser.add_argument("--freq", choices=sorted(SUPPORTED_FREQS), default=HERD_BACKFILL_FREQ)
    parser.add_argument("--source-period", default=HERD_BACKFILL_SOURCE_PERIOD)
    parser.add_argument("--overwrite", action="store_true", help="기존 score_date도 덮어쓰기")
    parser.add_argument("--dry-run", action="store_true", help="DB 저장 없이 계산만 수행")
    args = parser.parse_args()

    tickers = _normalize_tickers(args.tickers)
    if args.validation_universe:
        tickers = VALIDATION_TICKERS
    elif args.all_stocks:
        tickers = _fetch_tracked_tickers(include_stocks=True)
    elif args.all_tracked or not tickers:
        tickers = _fetch_tracked_tickers(include_stocks=False)

    if not tickers:
        logger.warning("백필할 티커가 없습니다.")
        return

    logger.info(f"백필 대상 {len(tickers)}개: {tickers}")
    summary = backfill_many(
        tickers,
        years=args.years,
        freq=args.freq,
        source_period=args.source_period,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )

    saved = sum(v[0] for v in summary.values())
    skipped = sum(v[1] for v in summary.values())
    failed = sum(v[2] for v in summary.values())
    logger.info(f"전체 백필 완료 | 저장 {saved}, 스킵 {skipped}, 실패 {failed}")


if __name__ == "__main__":
    main()
