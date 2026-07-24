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
  → 없거나 만료됐으면 즉시 계산 후 herd_scores에 저장
────────────────────────────────────────────────────────

실행:
    cd data/
    python scheduler/herd_scheduler.py             # 스케줄러 데몬으로 실행
    python scheduler/herd_scheduler.py --run-now   # 즉시 1회 실행 후 종료
"""

import argparse
import logging
import sys
from pathlib import Path

# data/ 하위에서 실행 시에도 패키지 import가 가능하도록 경로 추가
_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from collectors.price_collector import get_current_prices              # noqa: E402
from collectors.stock_collector import collect                          # noqa: E402
from config.database import create_db_engine, get_session_factory      # noqa: E402
from config.settings import (                                           # noqa: E402
    ALERT_NOTIFY_SUCCESS,
    ALERT_TIMEOUT_SECONDS,
    ALERT_WEBHOOK_URL,
    CACHE_DAYS,
    SCHEDULER_HOUR_ET,
    SCHEDULER_MINUTE_ET,
)
from scheduler.daemon import run_scheduler as start_scheduler                 # noqa: E402
from scheduler.incident_alerts import IncidentAlertConfig, send_scheduler_alert  # noqa: E402
from scheduler.on_demand import (                                             # noqa: E402
    calculate_many as calculate_many_cached,
    calculate_on_demand as calculate_cached,
)
from scheduler.run_history import SchedulerRunRecorder                          # noqa: E402
from scheduler.ticker_job import execute_tickers                                # noqa: E402
from scheduler.realtime_portfolio import calculate_current_portfolio as value_portfolio  # noqa: E402
from herd.calculator import run                                         # noqa: E402
from herd.portfolio_calculator import calculate_portfolio_value         # noqa: E402
from herd.saver import save_herd_result                                # noqa: E402
from init_db import (                                                   # noqa: E402
    UserPortfolio,
    UserWatchlist,
)

logger = logging.getLogger(__name__)

_SessionFactory = None


def _get_session_factory():
    """스케줄러 실행이나 DB 조회가 시작될 때 한 번만 연결한다."""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = get_session_factory(create_db_engine())
    return _SessionFactory

# on-demand 캐시를 식별하는 user_id
_CACHE_USER_ID = "cache"
_TIER1_JOB_NAME = "HERD_TIER1_DAILY"
_ALERT_CONFIG = IncidentAlertConfig(
    webhook_url=ALERT_WEBHOOK_URL,
    notify_success=ALERT_NOTIFY_SUCCESS,
    timeout_seconds=ALERT_TIMEOUT_SECONDS,
)


def _notify_scheduler_result(result: dict) -> None:
    """외부 알림 장애가 본 스케줄러 결과에 영향을 주지 않도록 격리한다."""
    try:
        send_scheduler_alert(result, _ALERT_CONFIG)
    except Exception as exc:
        logger.error("[Alert] 예상하지 못한 알림 오류: %s", exc, exc_info=True)


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
    with _get_session_factory()() as session:
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


def _start_scheduler_run(trigger_type: str) -> int | None:
    return SchedulerRunRecorder(_get_session_factory(), _TIER1_JOB_NAME).start(trigger_type)


def _finish_scheduler_run(
    run_id: int | None,
    status: str,
    total_count: int = 0,
    success_count: int = 0,
    failed_tickers: list[str] | None = None,
    error_message: str | None = None,
) -> None:
    SchedulerRunRecorder(_get_session_factory(), _TIER1_JOB_NAME).finish(
        run_id, status, total_count, success_count, failed_tickers, error_message,
    )


def run_herd_job(trigger_type: str = "SCHEDULED") -> dict:
    """
    Tier 1 전체 HERD 계산·저장 잡.
    collect → calculator.run → saver.save_herd_result 순서로 티커별 실행.
    개별 종목이 실패해도 다음 종목 처리를 계속 진행.
    """
    logger.info("━" * 60)
    logger.info("[Tier1] HERD 자동 계산 잡 시작")
    logger.info("━" * 60)
    run_id = _start_scheduler_run(trigger_type)

    # ── 1. 티커 목록 조회 ──────────────────────
    try:
        tickers = _fetch_tier1_tickers()
    except Exception as e:
        logger.error(f"[Tier1] 티커 목록 조회 실패 — 잡 중단: {e}", exc_info=True)
        _finish_scheduler_run(run_id, "FAILED", error_message=str(e))
        result = {"status": "FAILED", "total": 0, "success": [], "failed": []}
        _notify_scheduler_result(result)
        return result

    if not tickers:
        logger.warning(
            "[Tier1] 처리할 종목이 없습니다. "
            "user_portfolio 또는 user_watchlist에 종목을 추가하세요."
        )
        _finish_scheduler_run(run_id, "SUCCESS")
        result = {"status": "SUCCESS", "total": 0, "success": [], "failed": []}
        _notify_scheduler_result(result)
        return result

    # ── 2. 종목별 순차 처리 ────────────────────
    total = len(tickers)
    success_list, failed_list = execute_tickers(tickers, collect, run, save_herd_result)

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
    snapshot_error: str | None = None
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
        snapshot_error = str(e)

    if failed_list or snapshot_error:
        status = "FAILED" if total > 0 and not success_list else "PARTIAL_FAILURE"
    else:
        status = "SUCCESS"
    _finish_scheduler_run(
        run_id,
        status,
        total_count=total,
        success_count=len(success_list),
        failed_tickers=failed_list,
        error_message=snapshot_error,
    )
    result = {
        "status": status,
        "total": total,
        "success": success_list,
        "failed": failed_list,
    }
    _notify_scheduler_result(result)
    return result


# ══════════════════════════════════════════════
# Tier 2 — on-demand 실시간 계산 + 캐싱
# ══════════════════════════════════════════════

def calculate_on_demand(ticker: str, force: bool = False) -> dict:
    """호환 진입점: 캐시 조회와 계산은 on_demand 모듈에 위임한다."""
    return calculate_cached(
        ticker,
        force=force,
        cache_days=CACHE_DAYS,
        session_factory=_get_session_factory(),
        collect=collect,
        calculate=run,
        save=save_herd_result,
    )


def calculate_many_on_demand(tickers: list[str], force: bool = False) -> dict:
    """
    여러 티커의 HERD를 한 Python 프로세스 안에서 순차 갱신한다.
    Spring Boot 수동 새로고침에서 종목마다 프로세스를 새로 띄우는 비용을 줄이기 위한 배치 경로.
    """
    return calculate_many_cached(
        tickers,
        calculate_one=lambda ticker, should_force: calculate_on_demand(
            ticker,
            force=should_force,
        ),
        force=force,
    )


# ══════════════════════════════════════════════
# Tier 3 — on-demand 실시간 포트폴리오 계산
# ══════════════════════════════════════════════

def calculate_current_portfolio(user_id: str) -> dict:
    """호환 진입점: 실시간 평가는 realtime_portfolio 모듈에 위임한다."""
    return value_portfolio(
        user_id,
        session_factory=_get_session_factory(),
        price_loader=get_current_prices,
    )


# ══════════════════════════════════════════════
# 스케줄러 데몬 진입점
# ══════════════════════════════════════════════

def run_scheduler() -> None:
    """호환 진입점: 데몬 구성은 daemon 모듈에 위임한다."""
    start_scheduler(
        run_herd_job,
        hour_et=SCHEDULER_HOUR_ET,
        minute_et=SCHEDULER_MINUTE_ET,
    )


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
        run_herd_job(trigger_type="MANUAL")
    else:
        run_scheduler()
