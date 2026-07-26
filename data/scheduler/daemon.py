"""APScheduler 데몬 구성."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")
RETRYABLE_STATUSES = frozenset({"FAILED", "PARTIAL_FAILURE"})


def run_with_single_retry(job: Callable) -> dict:
    """예약 실행만 한 번 전체 재시도한다. 부분 프레임은 재사용하지 않는다."""
    try:
        first = job(trigger_type="SCHEDULED")
    except Exception:
        logger.exception("[Tier1] 예약 실행 중 처리되지 않은 오류가 발생했습니다.")
        return job(trigger_type="AUTOMATIC_RETRY")
    if first.get("status") not in RETRYABLE_STATUSES:
        return first
    logger.warning(
        "[Tier1] 예약 실행 상태가 %s여서 전체 작업을 한 번 재시도합니다.",
        first.get("status"),
    )
    return job(trigger_type="AUTOMATIC_RETRY")


def startup_catchup_due(
    latest_success_at: datetime | None,
    *,
    now: datetime,
    hour_et: int,
    minute_et: int,
) -> bool:
    """오늘 ET 예정 시각이 지났는데 그 이후 성공 실행이 없으면 보충 실행한다."""
    current_et = now.astimezone(ET)
    scheduled_et = current_et.replace(
        hour=hour_et,
        minute=minute_et,
        second=0,
        microsecond=0,
    )
    if current_et < scheduled_et:
        return False
    if latest_success_at is None:
        return True
    latest_utc = latest_success_at
    if latest_utc.tzinfo is None:
        latest_utc = latest_utc.replace(tzinfo=UTC)
    return latest_utc.astimezone(ET) < scheduled_et


def run_scheduler(
    job: Callable,
    *,
    hour_et: int,
    minute_et: int,
    latest_success_loader: Callable[[], datetime | None] | None = None,
    scheduler_factory=BlockingScheduler,
) -> None:
    """일일 HERD 작업을 미국 동부시간 기준으로 실행한다."""
    if latest_success_loader is not None:
        try:
            latest_success = latest_success_loader()
            if startup_catchup_due(
                latest_success,
                now=datetime.now(UTC),
                hour_et=hour_et,
                minute_et=minute_et,
            ):
                logger.warning("[Tier1] 오늘 예정 실행이 없어 기동 보충 실행을 시작합니다.")
                run_with_single_retry(
                    lambda trigger_type: job(
                        trigger_type=(
                            "STARTUP_CATCHUP"
                            if trigger_type == "SCHEDULED"
                            else trigger_type
                        )
                    )
                )
        except Exception:
            logger.exception("[Tier1] 기동 보충 실행 판정 실패 — 예약 데몬은 계속 시작합니다.")

    scheduler = scheduler_factory(timezone=ET)
    scheduler.add_job(
        func=run_with_single_retry,
        args=[job],
        trigger=CronTrigger(hour=hour_et, minute=minute_et, timezone=ET),
        id="herd_daily_job",
        name="HERD Tier1 일일 계산 잡",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=30 * 60,
    )
    logger.info("[Tier1] 스케줄러 시작 — 매일 %02d:%02d ET", hour_et, minute_et)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("[Tier1] 스케줄러 종료 요청")
        scheduler.shutdown(wait=False)
