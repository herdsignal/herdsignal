"""
scheduler/herd_scheduler.py — 장 마감 후 HERD 계산·저장 자동 스케줄러

실행:
    cd data/
    python scheduler/herd_scheduler.py             # 스케줄러 데몬으로 실행
    python scheduler/herd_scheduler.py --run-now   # 즉시 1회 실행 후 종료
"""

import argparse
import logging
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# data/ 하위에서 실행 시에도 패키지 import가 가능하도록 경로 추가
_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from collectors.stock_collector import collect        # noqa: E402
from config.database import create_db_engine, get_session_factory  # noqa: E402
from config.settings import SCHEDULER_HOUR_ET, SCHEDULER_MINUTE_ET  # noqa: E402
from herd.calculator import run                       # noqa: E402
from herd.saver import save_herd_result              # noqa: E402
from init_db import UserPortfolio, UserWatchlist      # noqa: E402

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 모듈 로드 시 DB 엔진·세션 팩토리 1회 초기화
# ──────────────────────────────────────────────
_engine         = create_db_engine()
_SessionFactory = get_session_factory(_engine)

# 미국 동부시간 타임존 (EDT/EST 자동 전환)
_ET = ZoneInfo("America/New_York")


# ──────────────────────────────────────────────
# 내부 헬퍼
# ──────────────────────────────────────────────
def _fetch_tickers() -> list[str]:
    """
    user_portfolio + user_watchlist 테이블에서 추적 대상 티커를 조회한다.
    두 테이블의 합집합을 사용하며 중복 제거 후 알파벳 오름차순 반환.
    """
    with _SessionFactory() as session:
        portfolio_tickers = {row.ticker for row in session.query(UserPortfolio).all()}
        watchlist_tickers = {row.ticker for row in session.query(UserWatchlist).all()}

    tickers = sorted(portfolio_tickers | watchlist_tickers)
    logger.info(
        f"대상 티커 {len(tickers)}개 "
        f"(포트폴리오 {len(portfolio_tickers)}개 + 관심종목 {len(watchlist_tickers)}개 → 합집합)"
    )
    if tickers:
        logger.info(f"  티커 목록: {tickers}")
    return tickers


# ──────────────────────────────────────────────
# 메인 잡
# ──────────────────────────────────────────────
def run_herd_job() -> None:
    """
    전체 HERD 계산·저장 잡.
    collect → calculator.run → saver.save_herd_result 순서로 티커별 실행.
    개별 종목이 실패해도 다음 종목 처리를 계속 진행.
    """
    logger.info("━" * 60)
    logger.info("HERD 자동 계산 잡 시작")
    logger.info("━" * 60)

    # ── 1. 티커 목록 조회 ──────────────────────
    try:
        tickers = _fetch_tickers()
    except Exception as e:
        logger.error(f"티커 목록 조회 실패 — 잡 중단: {e}", exc_info=True)
        return

    if not tickers:
        logger.warning(
            "처리할 종목이 없습니다. "
            "user_portfolio 또는 user_watchlist에 종목을 추가하세요."
        )
        return

    # ── 2. 종목별 순차 처리 ────────────────────
    success_list: list[str] = []
    failed_list:  list[str] = []
    total = len(tickers)

    for idx, ticker in enumerate(tickers, start=1):
        logger.info(f"[{ticker}] ─ 처리 시작 ({idx}/{total})")
        try:
            df          = collect(ticker)
            herd_result = run(ticker)
            ok          = save_herd_result(ticker, herd_result, df)

            if ok:
                success_list.append(ticker)
                logger.info(
                    f"[{ticker}] ✅ 완료 "
                    f"score={herd_result['score']:.2f}  stage={herd_result['stage']}"
                )
            else:
                # save_herd_result가 False를 반환하면 저장 실패(롤백 완료)
                failed_list.append(ticker)
                logger.error(f"[{ticker}] ❌ DB 저장 실패")

        except Exception as e:
            # 수집·계산 중 예외 발생 — 스택트레이스 포함 기록
            logger.error(f"[{ticker}] ❌ 처리 중 예외: {e}", exc_info=True)
            failed_list.append(ticker)

    # ── 3. 전체 결과 요약 ─────────────────────
    logger.info("━" * 60)
    logger.info(
        f"HERD 잡 완료 | 전체 {total}개 | "
        f"성공 {len(success_list)}개 | 실패 {len(failed_list)}개"
    )
    if success_list:
        logger.info(f"  ✅ 성공 종목: {success_list}")
    if failed_list:
        logger.error(f"  ❌ 실패 종목: {failed_list}")
    logger.info("━" * 60)


# ──────────────────────────────────────────────
# 스케줄러 데몬 진입점
# ──────────────────────────────────────────────
def run_scheduler() -> None:
    """
    APScheduler BlockingScheduler로 데몬 실행.
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
        name               = "HERD 일일 계산 잡",
        replace_existing   = True,
        max_instances      = 1,                  # 동시 실행 방지
        misfire_grace_time = 30 * 60,            # 30분 내 미실행 시 재시도
    )

    logger.info(
        f"스케줄러 시작 — 매일 {SCHEDULER_HOUR_ET:02d}:{SCHEDULER_MINUTE_ET:02d} ET에 실행 "
        f"(여름: 다음날 05:{SCHEDULER_MINUTE_ET:02d} KST | "
        f"겨울: 다음날 06:{SCHEDULER_MINUTE_ET:02d} KST)"
    )
    logger.info("종료하려면 Ctrl+C를 누르세요.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("스케줄러 종료 요청 — 정상 종료")
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
  python scheduler/herd_scheduler.py             스케줄러 데몬으로 실행
  python scheduler/herd_scheduler.py --run-now   즉시 1회 실행 후 종료
""",
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="스케줄 대기 없이 즉시 전체 실행 후 종료",
    )
    args = parser.parse_args()

    if args.run_now:
        logger.info("[--run-now] 즉시 실행 모드")
        run_herd_job()
    else:
        run_scheduler()
