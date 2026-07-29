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
import hashlib
import json
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
from scheduler.data_quality_gate import validate_operational_price_frame      # noqa: E402
from scheduler.incident_alerts import IncidentAlertConfig, send_scheduler_alert  # noqa: E402
from scheduler.on_demand import (                                             # noqa: E402
    calculate_many as calculate_many_cached,
    calculate_on_demand as calculate_cached,
)
from scheduler.run_history import SchedulerRunRecorder                          # noqa: E402
from scheduler.run_lock import SchedulerRunLock                                # noqa: E402
from scheduler.ticker_job import collect_ticker_frames, execute_tickers         # noqa: E402
from scheduler.realtime_portfolio import calculate_current_portfolio as value_portfolio  # noqa: E402
from scheduler.observation_s1 import (                                      # noqa: E402
    apply_operational_identity_window,
    build_observation_bundle,
    load_operational_identity_starts,
    required_collection_tickers,
    sector_etf_for_name,
    write_observation_bundle,
)
from scheduler.observation_store import save_observation_bundle             # noqa: E402
from scheduler.prospective_evidence import (                               # noqa: E402
    archived_tickers,
    archive_observation,
    mature_outcomes,
)
from scheduler.operation_log import write_operation_event                   # noqa: E402
from herd.calculator import run                                         # noqa: E402
from herd.portfolio_calculator import calculate_portfolio_value         # noqa: E402
from herd.saver import save_herd_result                                # noqa: E402
from init_db import (                                                   # noqa: E402
    Stock,
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
_RUN_LOCK_PATH = _DATA_DIR / "runtime" / "herd-tier1.lock"
_OPERATION_LOG_DIR = _DATA_DIR / "runtime" / "operations"
_ALERT_CONFIG = IncidentAlertConfig(
    webhook_url=ALERT_WEBHOOK_URL,
    notify_success=ALERT_NOTIFY_SUCCESS,
    timeout_seconds=ALERT_TIMEOUT_SECONDS,
)


def _notify_scheduler_result(result: dict) -> None:
    """외부 알림 장애가 본 스케줄러 결과에 영향을 주지 않도록 격리한다."""
    try:
        write_operation_event(result, output_dir=_OPERATION_LOG_DIR)
    except Exception as exc:
        logger.error("[Operations] 운영 사건 기록 실패: %s", exc, exc_info=True)
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
    # State S1의 참여도는 사용자 보유 종목 수가 아니라 고정 시장 peer
    # universe로 계산해야 하므로, 관찰 계약의 기준 종목과 섹터 ETF를
    # 매일 동일하게 수집한다.
    all_tickers |= required_collection_tickers()
    tickers = sorted(all_tickers)

    logger.info(
        f"[Tier1] 대상 티커 {len(tickers)}개 "
        f"(포트폴리오 {len(portfolio_tickers)}개 + "
        f"관심종목 {len(watchlist_tickers)}개 → 합집합 + SPY)"
    )
    return tickers


def _fetch_operational_tickers() -> list[str]:
    """구형 v4 저장이 필요한 실제 보유·관심 종목과 SPY만 반환한다."""
    with _get_session_factory()() as session:
        portfolio = {
            row.ticker
            for row in session.query(UserPortfolio)
            .filter(UserPortfolio.user_id != _CACHE_USER_ID)
            .all()
        }
        watchlist = {
            row.ticker
            for row in session.query(UserWatchlist).all()
        }
    return sorted(portfolio | watchlist | {"SPY"})


def _fetch_portfolio_user_ids() -> list[str]:
    """평가 가능한 보유 종목이 있는 모든 사용자를 반환한다."""
    with _get_session_factory()() as session:
        rows = (
            session.query(UserPortfolio.user_id)
            .filter(
                UserPortfolio.avg_price.isnot(None),
                UserPortfolio.quantity.isnot(None),
                UserPortfolio.quantity > 0,
            )
            .distinct()
            .all()
        )
    return sorted({str(row[0]) for row in rows if row[0]})


def _snapshot_all_portfolios() -> dict:
    """사용자별 오류를 격리해 일별 포트폴리오 스냅샷을 저장한다."""
    user_ids = _fetch_portfolio_user_ids()
    saved: list[str] = []
    errors: list[str] = []
    for user_id in user_ids:
        try:
            result = calculate_portfolio_value(user_id)
            if result["stocks"]:
                saved.append(user_id)
                logger.info(
                    "[Tier1] 포트폴리오 스냅샷 저장 — 사용자 %s, 보유 %s종목, 총 평가 $%s",
                    user_id,
                    len(result["stocks"]),
                    f"{result['total_value']:,.2f}",
                )
        except Exception as exc:
            errors.append(f"{user_id}: {exc}")
            logger.error(
                "[Tier1] 사용자 %s 포트폴리오 스냅샷 저장 실패: %s",
                user_id,
                exc,
                exc_info=True,
            )
    if not user_ids:
        logger.info("[Tier1] 평가 가능한 포트폴리오 없음 — 스냅샷 생략")
    return {"requested": user_ids, "saved": saved, "errors": errors}


def _start_scheduler_run(trigger_type: str) -> int | None:
    return SchedulerRunRecorder(_get_session_factory(), _TIER1_JOB_NAME).start(trigger_type)


def _record_scheduler_universe(run_id: int | None, universe_sha256: str) -> None:
    SchedulerRunRecorder(
        _get_session_factory(), _TIER1_JOB_NAME
    ).record_universe(run_id, universe_sha256)


def _finish_scheduler_run(
    run_id: int | None,
    status: str,
    total_count: int = 0,
    success_count: int = 0,
    failed_tickers: list[str] | None = None,
    skipped_tickers: list[str] | None = None,
    publish_status: str | None = None,
    observation_count: int | None = None,
    error_message: str | None = None,
) -> None:
    SchedulerRunRecorder(_get_session_factory(), _TIER1_JOB_NAME).finish(
        run_id,
        status,
        total_count,
        success_count,
        failed_tickers,
        skipped_tickers,
        publish_status,
        observation_count,
        error_message,
    )


def _fetch_sector_overrides() -> dict[str, str]:
    """고정 연구 universe 밖의 보유 종목을 명시적인 섹터 ETF에 연결한다."""
    with _get_session_factory()() as session:
        return {
            row.ticker: sector
            for row in session.query(Stock).all()
            if (sector := sector_etf_for_name(row.sector)) is not None
        }


def _fetch_tracking_scopes() -> dict[str, set[str]]:
    """개인 식별자 없이 관측 당시 보유·관심 범위만 고정한다."""
    scopes: dict[str, set[str]] = {}
    with _get_session_factory()() as session:
        portfolio = {
            str(row[0]).strip().upper()
            for row in session.query(UserPortfolio.ticker)
            .filter(UserPortfolio.user_id != _CACHE_USER_ID)
            .distinct()
            .all()
            if row[0]
        }
        watchlist = {
            str(row[0]).strip().upper()
            for row in session.query(UserWatchlist.ticker).distinct().all()
            if row[0]
        }
    for ticker in portfolio:
        scopes.setdefault(ticker, set()).add("PORTFOLIO")
    for ticker in watchlist:
        scopes.setdefault(ticker, set()).add("WATCHLIST")
    return scopes


def _record_prospective_evidence(
    bundle: dict | None,
    observation_frames: dict,
) -> dict:
    archive = (
        archive_observation(
            bundle,
            observation_frames,
            _fetch_tracking_scopes(),
        )
        if bundle is not None
        else {
            "status": "SKIPPED_NO_NEW_OBSERVATION",
            "recordCount": 0,
        }
    )
    maturity = mature_outcomes(observation_frames)
    logger.info(
        "[Tier1] prospective evidence — 관측 %s, 성숙 신규 %s, 대기 %s",
        archive["status"],
        maturity["created"],
        maturity["pending"],
    )
    return {"archive": archive, "maturity": maturity}


def _complete_prospective_outcome_frames(
    observation_frames: dict,
) -> tuple[dict, list[str]]:
    """현재 추적 범위에서 빠진 과거 관측 종목도 만기까지 가격을 수집한다."""
    missing = sorted(archived_tickers() - set(observation_frames))
    if not missing:
        return observation_frames, []
    logger.info(
        "[Tier1] prospective 과거 관측 %s종목 결과 추적 보충 수집",
        len(missing),
    )
    supplemental, failed = collect_ticker_frames(
        missing,
        collect,
        validate=validate_operational_price_frame,
    )
    return {**observation_frames, **supplemental}, failed


def _build_and_write_observation(
    observation_frames: dict,
    success_list: list[str],
) -> dict:
    bundle = build_observation_bundle(
        observation_frames,
        target_tickers=set(success_list),
        sector_overrides=_fetch_sector_overrides(),
    )
    write_observation_bundle(bundle)
    save_result = save_observation_bundle(bundle, _get_session_factory())
    logger.info(
        "[Tier1] State S1 관찰 DB 저장 — 신규 %s, 갱신 %s",
        save_result["inserted"],
        save_result["updated"],
    )
    return bundle


def _run_herd_job_unlocked(trigger_type: str) -> dict:
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

    universe_sha256 = hashlib.sha256(
        ("\n".join(tickers) + "\n").encode("utf-8")
    ).hexdigest()
    _record_scheduler_universe(run_id, universe_sha256)

    # ── 2. S1 가격 수집과 구형 v4 운영 계산을 분리 ────────────────
    total = len(tickers)
    identity_starts = load_operational_identity_starts()
    observation_frames, collection_failed = collect_ticker_frames(
        tickers,
        collect,
        validate=validate_operational_price_frame,
        transform=lambda ticker, frame: apply_operational_identity_window(
            ticker,
            frame,
            starts=identity_starts,
        ),
    )
    try:
        operational_scope = set(_fetch_operational_tickers())
    except Exception as exc:
        # 운영 범위 조회 실패 시 점수를 누락하지 않도록 기존 전체 계산으로
        # 보수적으로 폴백한다. 속도보다 사용자 화면의 연속성을 우선한다.
        logger.error(
            "[Tier1] 운영 종목 범위 조회 실패 — 전체 v4 계산으로 폴백: %s",
            exc,
            exc_info=True,
        )
        operational_scope = set(observation_frames)
    operational_tickers = sorted(
        operational_scope.intersection(observation_frames)
    )
    _, legacy_failed, skipped_list = execute_tickers(
        operational_tickers,
        collect=lambda ticker: observation_frames[ticker],
        calculate=run,
        save=save_herd_result,
    )
    success_list = sorted(
        set(observation_frames) - set(legacy_failed) - set(skipped_list)
    )
    failed_list = sorted(set(collection_failed) | set(legacy_failed))

    # ── 3. State S1·Transition S1 관찰 번들 생성 ─────────────────
    observation_error: str | None = None
    prospective_error: str | None = None
    observation_count: int | None = None
    prospective_result: dict | None = None
    bundle: dict | None = None
    publish_status = "SUCCESS"
    try:
        # 단일 종목 실패가 아니라 잠긴 계약의 90% coverage 게이트가
        # S1 발행 가능 여부를 결정한다.
        bundle = _build_and_write_observation(
            observation_frames, sorted(observation_frames)
        )
        observation_count = len(bundle["records"])
        logger.info(
            "[Tier1] State S1 관찰 번들 생성 완료 — %s종목, 기준 %s",
            len(bundle["records"]),
            bundle["records"]["SPY"]["asOfDate"],
        )
    except Exception as exc:
        observation_error = str(exc)
        publish_status = "FAILED"
        logger.error(
            "[Tier1] State S1 관찰 번들 생성 실패: %s",
            exc,
            exc_info=True,
        )
    try:
        # 새 S1 발행이 차단된 날에도 이전 관측의 21·63·126일 결과는
        # 가능한 종목부터 성숙시킨다. 새 관측 생성과 결과 성숙의 장애
        # 경계를 분리해 단일 종목 수집 실패가 기존 원장을 멈추지 않게 한다.
        outcome_frames, outcome_collection_failed = (
            _complete_prospective_outcome_frames(observation_frames)
        )
        prospective_result = _record_prospective_evidence(
            bundle, outcome_frames
        )
        prospective_result["outcomeCollectionFailed"] = outcome_collection_failed
        if prospective_result["archive"]["status"] == "CONFLICT_REJECTED":
            prospective_error = prospective_result["archive"]["reason"]
    except Exception as exc:
        prospective_error = str(exc)
        logger.error(
            "[Tier1] prospective evidence 기록/성숙 실패: %s",
            exc,
            exc_info=True,
        )

    # ── 4. 전체 결과 요약 ─────────────────────
    logger.info("━" * 60)
    logger.info(
        f"[Tier1] 잡 완료 | 전체 {total}개 | "
        f"성공 {len(success_list)}개 | 실패 {len(failed_list)}개"
    )
    if success_list:
        logger.info(f"[Tier1]   ✅ 성공: {success_list}")
    if failed_list:
        logger.error(f"[Tier1]   ❌ 실패: {failed_list}")
    if skipped_list:
        logger.warning(f"[Tier1]   ⏭️ 최소 이력 미달 제외: {skipped_list}")
    logger.info("━" * 60)

    # ── 5. 모든 사용자의 포트폴리오 스냅샷 저장 ────────────────────
    # HERD 잡 완료 후 오늘의 포트폴리오 평가금액을 portfolio_history에 기록
    snapshot_error: str | None = None
    try:
        snapshot_result = _snapshot_all_portfolios()
        if snapshot_result["errors"]:
            snapshot_error = "; ".join(snapshot_result["errors"])
    except Exception as e:
        # 포트폴리오 저장 실패가 HERD 잡 전체를 중단시키지 않도록 예외 격리
        logger.error(f"[Tier1] 포트폴리오 스냅샷 저장 실패: {e}", exc_info=True)
        snapshot_error = str(e)

    combined_error = "; ".join(
        item
        for item in (observation_error, prospective_error, snapshot_error)
        if item
    ) or None
    if failed_list or combined_error:
        status = "FAILED" if total > 0 and not success_list else "PARTIAL_FAILURE"
    else:
        status = "SUCCESS"
    _finish_scheduler_run(
        run_id,
        status,
        total_count=total,
        success_count=len(success_list),
        failed_tickers=failed_list,
        skipped_tickers=skipped_list,
        publish_status=publish_status,
        observation_count=observation_count,
        error_message=combined_error,
    )
    result = {
        "status": status,
        "total": total,
        "success": success_list,
        "failed": failed_list,
        "skipped": skipped_list,
        "observation": (
            publish_status
        ),
        "universeSha256": universe_sha256,
    }
    if prospective_result is not None:
        result["prospectiveEvidence"] = prospective_result
    _notify_scheduler_result(result)
    return result


def run_herd_job(trigger_type: str = "SCHEDULED") -> dict:
    lock = SchedulerRunLock.try_acquire(_RUN_LOCK_PATH)
    if lock is None:
        logger.warning("[Tier1] 이미 실행 중인 작업이 있어 중복 실행을 건너뜁니다.")
        return {
            "status": "DUPLICATE_SKIPPED",
            "total": 0,
            "success": [],
            "failed": [],
            "skipped": [],
            "observation": "NOT_ATTEMPTED",
        }
    try:
        return _run_herd_job_unlocked(trigger_type)
    finally:
        lock.release()


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
        latest_success_loader=lambda: SchedulerRunRecorder(
            _get_session_factory(),
            _TIER1_JOB_NAME,
        ).latest_success_at(),
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
  python scheduler/herd_scheduler.py --retry-now 실패 후 전체 원자 재시도
""",
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="스케줄 대기 없이 즉시 Tier1 전체 실행 후 종료",
    )
    parser.add_argument(
        "--retry-now",
        action="store_true",
        help="부분 프레임을 재사용하지 않고 Tier1 전체를 다시 실행",
    )
    args = parser.parse_args()

    if args.run_now or args.retry_now:
        logger.info("[--run-now] Tier1 즉시 실행 모드")
        result = run_herd_job(trigger_type="RETRY" if args.retry_now else "MANUAL")
        print(json.dumps(result, ensure_ascii=False))
    else:
        run_scheduler()
