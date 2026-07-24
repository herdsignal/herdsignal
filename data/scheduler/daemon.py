"""APScheduler 데몬 구성."""

from __future__ import annotations

import logging
from collections.abc import Callable
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")


def run_scheduler(
    job: Callable,
    *,
    hour_et: int,
    minute_et: int,
    scheduler_factory=BlockingScheduler,
) -> None:
    """일일 HERD 작업을 미국 동부시간 기준으로 실행한다."""
    scheduler = scheduler_factory(timezone=ET)
    scheduler.add_job(
        func=job,
        kwargs={"trigger_type": "SCHEDULED"},
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
