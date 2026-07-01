"""
scheduler/herd_scheduler.py — HERD 계산 스케줄러 + on-demand 캐시

────────────────────────────────────────────────────────
Tier 1 — 매일 자동 업데이트 (run_herd_job)
  대상: user_portfolio + user_watchlist 전체 (cache 제외) + SPY 고정
  → 유저가 포트폴리오/관심종목에 추가한 모든 종목 자동 포함
  → 새 종목 추가 시 다음날부터 자동 업데이트 시작
  → 매일 16:30 ET 자동 실행

Tier 2 — 검색 시 실시간 계산 + 캐싱 (calculate_on_demand)
  대상: 검색/조회 요청이 들어온 임의의 티커
  → 7일 이내 데이터가 있으면 캐시 반환 (재계산 없음)
  → 없거나 만료됐으면 즉시 계산 후 user_id='cache'로 저장
────────────────────────────────────────────────────────

실행:
    cd data/
    python scheduler/herd_scheduler.py             # 스케줄러 데몬으로 실행
    python scheduler/herd_scheduler.py --run-now   # 즉시 1회 실행 후 종료
"""

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# data/ 하위에서 실행 시에도 패키지 import가 가능하도록 경로 추가
_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from collectors.price_collector import get_current_prices              # noqa: E402
from collectors.stock_collector import collect                          # noqa: E402
from config.database import create_db_engine, get_session_factory      # noqa: E402
from config.settings import (                                           # noqa: E402
    CACHE_DAYS,
    SCHEDULER_HOUR_ET,
    SCHEDULER_MINUTE_ET,
)
from herd.calculator import run                                         # noqa: E402
from herd.portfolio_calculator import calculate_portfolio_value         # noqa: E402
from herd.saver import save_herd_result                                # noqa: E402
from init_db import (                                                   # noqa: E402
    HerdIndicator,
    HerdScore,
    PortfolioHistory,
    UserPortfolio,
    UserWatchlist,
)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 모듈 로드 시 DB 엔진·세션 팩토리 1회 초기화
# ──────────────────────────────────────────────
_engine         = create_db_engine()
_SessionFactory = get_session_factory(_engine)

# 미국 동부시간 타임존 (EDT/EST 자동 전환)
_ET = ZoneInfo("America/New_York")

# on-demand 캐시를 식별하는 user_id
_CACHE_USER_ID = "cache"


# ══════════════════════════════════════════════
# Tier 1 — 매일 자동 업데이트
# ══════════════════════════════════════════════

def _fetch_tier1_tickers() -> list[str]:
    """
    Tier 1 자동 스케줄링 대상 티커를 동적으로 조회한다.

    수집 범위:
      - user_portfolio 전체 (user_id = 'cache' 제외)
      - user_watchlist 전체
      - SPY 고정 포함 (벤치마크)

    유저가 포트폴리오/관심종목에 종목을 추가하면
    별도 설정 변경 없이 다음 스케줄 실행 시 자동으로 대상에 포함된다.
    중복 제거 후 알파벳 오름차순 반환.
    """
    with _SessionFactory() as session:
        # user_portfolio: cache 사용자 제외한 전체
        portfolio_tickers = {
            row.ticker
            for row in session.query(UserPortfolio)
            .filter(UserPortfolio.user_id != _CACHE_USER_ID)
            .all()
        }
        # user_watchlist: 전체 (user_id 구분 없이)
        watchlist_tickers = {
            row.ticker
            for row in session.query(UserWatchlist)
            .all()
        }

    # SPY는 spy_benchmark로 이미 포함되지만 명시적으로 보장
    all_tickers = portfolio_tickers | watchlist_tickers | {"SPY"}
    tickers = sorted(all_tickers)

    logger.info(
        f"[Tier1] 대상 티커 {len(tickers)}개 "
        f"(포트폴리오 {len(portfolio_tickers)}개 + "
        f"관심종목 {len(watchlist_tickers)}개 → 합집합 + SPY)"
    )
    return tickers


def run_herd_job() -> None:
    """
    Tier 1 전체 HERD 계산·저장 잡.
    collect → calculator.run → saver.save_herd_result 순서로 티커별 실행.
    개별 종목이 실패해도 다음 종목 처리를 계속 진행.
    """
    logger.info("━" * 60)
    logger.info("[Tier1] HERD 자동 계산 잡 시작")
    logger.info("━" * 60)

    # ── 1. 티커 목록 조회 ──────────────────────
    try:
        tickers = _fetch_tier1_tickers()
    except Exception as e:
        logger.error(f"[Tier1] 티커 목록 조회 실패 — 잡 중단: {e}", exc_info=True)
        return

    if not tickers:
        logger.warning(
            "[Tier1] 처리할 종목이 없습니다. "
            "user_portfolio 또는 user_watchlist에 종목을 추가하세요."
        )
        return

    # ── 2. 종목별 순차 처리 ────────────────────
    success_list: list[str] = []
    failed_list:  list[str] = []
    total = len(tickers)

    for idx, ticker in enumerate(tickers, start=1):
        logger.info(f"[Tier1][{ticker}] ─ 처리 시작 ({idx}/{total})")
        try:
            df          = collect(ticker)
            herd_result = run(ticker)
            ok          = save_herd_result(ticker, herd_result, df)

            if ok:
                success_list.append(ticker)
                logger.info(
                    f"[Tier1][{ticker}] ✅ 완료 "
                    f"score={herd_result['score']:.2f}  stage={herd_result['stage']}"
                )
            else:
                failed_list.append(ticker)
                logger.error(f"[Tier1][{ticker}] ❌ DB 저장 실패")

        except Exception as e:
            logger.error(f"[Tier1][{ticker}] ❌ 처리 중 예외: {e}", exc_info=True)
            failed_list.append(ticker)

    # ── 3. 전체 결과 요약 ─────────────────────
    logger.info("━" * 60)
    logger.info(
        f"[Tier1] 잡 완료 | 전체 {total}개 | "
        f"성공 {len(success_list)}개 | 실패 {len(failed_list)}개"
    )
    if success_list:
        logger.info(f"[Tier1]   ✅ 성공: {success_list}")
    if failed_list:
        logger.error(f"[Tier1]   ❌ 실패: {failed_list}")
    logger.info("━" * 60)

    # ── 4. 포트폴리오 스냅샷 저장 (local 사용자) ───────────────────
    # HERD 잡 완료 후 오늘의 포트폴리오 평가금액을 portfolio_history에 기록
    try:
        result = calculate_portfolio_value("local")
        if result["stocks"]:
            logger.info(
                f"[Tier1] 포트폴리오 스냅샷 저장 완료 — "
                f"보유 {len(result['stocks'])}종목  "
                f"총 평가 ${result['total_value']:,.2f}  "
                f"수익률 {result['total_return_pct']:.2f}%"
            )
        else:
            logger.info("[Tier1] 포트폴리오 보유 종목 없음 — 스냅샷 생략")
    except Exception as e:
        # 포트폴리오 저장 실패가 HERD 잡 전체를 중단시키지 않도록 예외 격리
        logger.error(f"[Tier1] 포트폴리오 스냅샷 저장 실패: {e}", exc_info=True)


# ══════════════════════════════════════════════
# Tier 2 — on-demand 실시간 계산 + 캐싱
# ══════════════════════════════════════════════

def calculate_on_demand(ticker: str) -> dict:
    """
    Tier 2: 요청 시 실시간 HERD 계산 + 캐싱.

    동작 흐름:
      1. herd_scores 테이블에서 해당 ticker의 최신 데이터 조회
      2. CACHE_DAYS(7일) 이내 데이터 있음 → 캐시에서 바로 반환 (재계산 없음)
      3. 데이터 없거나 7일 이상 지남 → 즉시 계산 후 DB 저장
         - user_portfolio에 user_id='cache'로 티커 등록 (없으면)
         - herd_scores / herd_indicators / daily_prices / stocks 업데이트

    Args:
        ticker: 종목 티커 (예: "RKLB", "AAPL")

    Returns:
        {
            "ticker":     str,    # 티커
            "score":      float,  # HERD 점수 (0~100)
            "stage":      str,    # 단계 (Flee/Scatter/Calm/Drift/Rush)
            "signal":     str,    # 매매 신호 (BUY/ADD/HOLD/REDUCE/SELL)
            "indicators": dict,   # 5개 지표 분해값
            "score_date": str,    # 기준 날짜 (YYYY-MM-DD)
            "from_cache": bool,   # True = 캐시 반환, False = 신규 계산
        }
    """
    ticker = ticker.upper().strip()
    cache_cutoff = date.today() - timedelta(days=CACHE_DAYS)

    # ── 1. 캐시 확인 ──────────────────────────
    with _SessionFactory() as session:
        latest_score = (
            session.query(HerdScore)
            .filter(HerdScore.ticker == ticker)
            .order_by(HerdScore.score_date.desc())
            .first()
        )

        if latest_score and latest_score.score_date >= cache_cutoff:
            # 캐시 히트 — 지표 분해값도 조회
            ind_row = (
                session.query(HerdIndicator)
                .filter(
                    HerdIndicator.ticker     == ticker,
                    HerdIndicator.score_date == latest_score.score_date,
                )
                .first()
            )

            # Decimal 타입을 float으로 변환해 반환
            indicators: dict = {}
            if ind_row:
                indicators = {
                    "weekly_rsi":      float(ind_row.weekly_rsi or 0),
                    "monthly_rsi":     float(ind_row.monthly_rsi or 0),
                    "position_52w":    float(ind_row.position_52w or 0),
                    "ma200_deviation": float(ind_row.ma200_deviation or 0),
                    "volume_strength": float(ind_row.volume_strength or 0),
                }

            logger.info(
                f"[Tier2][{ticker}] 캐시 히트 — "
                f"score_date={latest_score.score_date}  "
                f"score={float(latest_score.herd_score):.2f}"
            )
            return {
                "ticker":     ticker,
                "score":      float(latest_score.herd_score),
                "stage":      latest_score.herd_stage,
                "signal":     latest_score.signal or "HOLD",
                "indicators": indicators,
                "score_date": str(latest_score.score_date),
                "from_cache": True,
            }

    # ── 2. 캐시 미스 또는 만료 → 즉시 계산 ──────
    logger.info(
        f"[Tier2][{ticker}] 캐시 미스 — "
        f"(최신={latest_score.score_date if latest_score else '없음'}) "
        f"실시간 계산 시작"
    )

    # user_portfolio에 cache 사용자로 티커 등록 (없으면 INSERT)
    with _SessionFactory() as session:
        cache_entry = session.query(UserPortfolio).filter_by(
            user_id=_CACHE_USER_ID, ticker=ticker
        ).first()
        if not cache_entry:
            session.add(UserPortfolio(user_id=_CACHE_USER_ID, ticker=ticker))
            session.commit()
            logger.info(f"[Tier2][{ticker}] user_portfolio에 캐시 티커 등록")

    # 데이터 수집 + HERD 계산 + DB 저장
    df          = collect(ticker)
    herd_result = run(ticker)
    save_herd_result(ticker, herd_result, df)

    logger.info(
        f"[Tier2][{ticker}] ✅ 계산 완료 — "
        f"score={herd_result['score']:.2f}  stage={herd_result['stage']}"
    )

    return {
        "ticker":     ticker,
        "score":      herd_result["score"],
        "stage":      herd_result["stage"],
        "signal":     herd_result.get("signal", "HOLD"),
        "indicators": herd_result["indicators"],
        "score_date": str(date.today()),
        "from_cache": False,
    }


# ══════════════════════════════════════════════
# Tier 3 — on-demand 실시간 포트폴리오 계산
# ══════════════════════════════════════════════

def calculate_current_portfolio(user_id: str) -> dict:
    """
    yfinance 실시간 현재가(15분 지연)로 포트폴리오 평가금액을 즉시 계산한다.

    daily_prices DB를 거치지 않으므로 장중에도 최신 가격 반영 가능.
    계산 결과는 portfolio_history에 UPSERT (오늘 날짜 스냅샷 갱신).

    동작 흐름:
      1. user_portfolio에서 avg_price·quantity가 모두 있는 종목만 조회
      2. get_current_prices()로 yfinance 현재가 일괄 조회
      3. 종목별 market_value·return_pct·daily_change_pct 계산
      4. 전체 합산 지표 산출
      5. portfolio_history UPSERT 후 결과 반환

    Args:
        user_id: 사용자 ID (MVP 기본값 'local')

    Returns:
        {
            "total_value":      float,  # 총 평가금액 (USD)
            "total_cost":       float,  # 총 매입금액 (USD)
            "total_return_pct": float,  # 총 수익률 (%)
            "daily_change_pct": float,  # 포트폴리오 일일 등락률 (%)
            "stocks": [
                {
                    "ticker":           str,
                    "avg_price":        float,
                    "quantity":         float,
                    "current_price":    float,
                    "market_value":     float,
                    "return_pct":       float,
                    "daily_change_pct": float,
                }
            ]
        }
    """
    today = date.today()

    # ── 1. 보유 종목 조회 (avg_price·quantity 모두 있는 것만) ──────────────
    with _SessionFactory() as session:
        holdings = (
            session.query(UserPortfolio)
            .filter(
                UserPortfolio.user_id    == user_id,
                UserPortfolio.avg_price.isnot(None),
                UserPortfolio.quantity.isnot(None),
            )
            .order_by(UserPortfolio.ticker)
            .all()
        )
        # 세션 종료 전 필요한 값 추출 (lazy loading 방지)
        holdings_data = [
            {
                "ticker":    h.ticker,
                "avg_price": float(h.avg_price),
                "quantity":  float(h.quantity),
            }
            for h in holdings
        ]

    if not holdings_data:
        logger.warning(f"[Tier3][{user_id}] avg_price·quantity가 있는 보유 종목 없음")
        return {
            "total_value":      0.0,
            "total_cost":       0.0,
            "total_return_pct": 0.0,
            "daily_change_pct": 0.0,
            "stocks":           [],
        }

    tickers = [h["ticker"] for h in holdings_data]
    logger.info(f"[Tier3][{user_id}] 실시간 조회 대상: {tickers}")

    # ── 2. yfinance 현재가 일괄 조회 ──────────────────────────────────────
    prices = get_current_prices(tickers)

    # ── 3. 종목별 계산 ────────────────────────────────────────────────────
    stocks:         list  = []
    total_value:    float = 0.0
    total_cost:     float = 0.0
    prev_total:     float = 0.0   # 전일 총액 (포트폴리오 일일 등락 계산용)
    curr_for_daily: float = 0.0   # 현재 총액 (전일 데이터 있는 종목만)

    for h in holdings_data:
        ticker    = h["ticker"]
        avg_price = h["avg_price"]
        quantity  = h["quantity"]
        price_data = prices.get(ticker)

        if price_data is None:
            logger.warning(f"[Tier3][{ticker}] 현재가 조회 실패 — 계산 제외")
            continue

        current_price    = price_data["price"]
        prev_close       = price_data["prev_close"]
        daily_change_pct = price_data["change_pct"]

        market_value = current_price * quantity
        cost         = avg_price * quantity
        return_pct   = (current_price - avg_price) / avg_price * 100

        total_value    += market_value
        total_cost     += cost
        prev_total     += prev_close * quantity
        curr_for_daily += current_price * quantity

        stocks.append({
            "ticker":           ticker,
            "avg_price":        avg_price,
            "quantity":         quantity,
            "current_price":    round(current_price,    4),
            "market_value":     round(market_value,     2),
            "return_pct":       round(return_pct,       4),
            "daily_change_pct": round(daily_change_pct, 4),
        })

    if not stocks:
        logger.warning(f"[Tier3][{user_id}] 유효한 현재가가 있는 종목 없음")
        return {
            "total_value":      0.0,
            "total_cost":       0.0,
            "total_return_pct": 0.0,
            "daily_change_pct": 0.0,
            "stocks":           [],
        }

    # ── 4. 전체 합산 지표 산출 ────────────────────────────────────────────
    total_return_pct = (total_value - total_cost) / total_cost * 100 if total_cost > 0 else 0.0
    portfolio_daily  = (
        (curr_for_daily - prev_total) / prev_total * 100
        if prev_total > 0 else 0.0
    )

    # ── 5. portfolio_history UPSERT (오늘 날짜) ───────────────────────────
    with _SessionFactory() as session:
        existing = (
            session.query(PortfolioHistory)
            .filter_by(user_id=user_id, snapshot_date=today)
            .first()
        )
        if existing:
            existing.total_value      = round(total_value, 2)
            existing.total_cost       = round(total_cost,  2)
            existing.total_return_pct = round(total_return_pct, 4)
        else:
            session.add(PortfolioHistory(
                user_id          = user_id,
                snapshot_date    = today,
                total_value      = round(total_value, 2),
                total_cost       = round(total_cost,  2),
                total_return_pct = round(total_return_pct, 4),
            ))
        session.commit()

    logger.info(
        f"[Tier3][{user_id}] 실시간 계산 완료 — "
        f"보유 {len(stocks)}종목  "
        f"총 평가 ${total_value:,.2f}  수익률 {total_return_pct:.2f}%"
    )

    return {
        "total_value":      round(total_value, 2),
        "total_cost":       round(total_cost,  2),
        "total_return_pct": round(total_return_pct, 4),
        "daily_change_pct": round(portfolio_daily,  4),
        "stocks":           stocks,
    }


# ══════════════════════════════════════════════
# 스케줄러 데몬 진입점
# ══════════════════════════════════════════════

def run_scheduler() -> None:
    """
    APScheduler BlockingScheduler로 Tier 1 데몬 실행.
    미국 동부시간(ET) 기준 매일 SCHEDULER_HOUR_ET:SCHEDULER_MINUTE_ET에 run_herd_job 실행.
    - 여름(EDT) 16:30 ET = 다음날 05:30 KST
    - 겨울(EST) 16:30 ET = 다음날 06:30 KST
    """
    scheduler = BlockingScheduler(timezone=_ET)

    scheduler.add_job(
        func               = run_herd_job,
        trigger            = CronTrigger(
            hour     = SCHEDULER_HOUR_ET,
            minute   = SCHEDULER_MINUTE_ET,
            timezone = _ET,
        ),
        id                 = "herd_daily_job",
        name               = "HERD Tier1 일일 계산 잡",
        replace_existing   = True,
        max_instances      = 1,          # 동시 실행 방지
        misfire_grace_time = 30 * 60,   # 30분 내 미실행 시 재시도
    )

    logger.info(
        f"[Tier1] 스케줄러 시작 — "
        f"매일 {SCHEDULER_HOUR_ET:02d}:{SCHEDULER_MINUTE_ET:02d} ET에 실행 "
        f"(여름: 다음날 05:{SCHEDULER_MINUTE_ET:02d} KST | "
        f"겨울: 다음날 06:{SCHEDULER_MINUTE_ET:02d} KST)"
    )
    logger.info("종료하려면 Ctrl+C를 누르세요.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("[Tier1] 스케줄러 종료 요청 — 정상 종료")
        scheduler.shutdown(wait=False)


# ──────────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="HerdSignal HERD 자동 계산 스케줄러",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예:
  python scheduler/herd_scheduler.py             Tier1 스케줄러 데몬으로 실행
  python scheduler/herd_scheduler.py --run-now   Tier1 즉시 1회 실행 후 종료
""",
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="스케줄 대기 없이 즉시 Tier1 전체 실행 후 종료",
    )
    args = parser.parse_args()

    if args.run_now:
        logger.info("[--run-now] Tier1 즉시 실행 모드")
        run_herd_job()
    else:
        run_scheduler()
