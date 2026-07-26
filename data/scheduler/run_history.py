"""스케줄러 실행 이력의 시작·완료 트랜잭션을 관리한다."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Callable

from init_db import SchedulerRun

logger = logging.getLogger(__name__)


class SchedulerRunRecorder:
    def __init__(self, session_factory: Callable, job_name: str):
        self._session_factory = session_factory
        self._job_name = job_name

    def start(self, trigger_type: str) -> int | None:
        """실행 시작을 별도 트랜잭션으로 기록한다."""
        try:
            with self._session_factory() as session:
                row = SchedulerRun(
                    job_name=self._job_name,
                    trigger_type=trigger_type,
                    status="RUNNING",
                    started_at=datetime.now(UTC).replace(tzinfo=None),
                )
                session.add(row)
                session.commit()
                return row.id
        except Exception as exc:
            logger.error("스케줄러 실행 시작 이력 저장 실패: %s", exc, exc_info=True)
            return None

    def latest_success_at(self) -> datetime | None:
        """가장 최근 정상 완료 시각을 반환한다."""
        try:
            with self._session_factory() as session:
                row = (
                    session.query(SchedulerRun)
                    .filter(
                        SchedulerRun.job_name == self._job_name,
                        SchedulerRun.status == "SUCCESS",
                        SchedulerRun.finished_at.isnot(None),
                    )
                    .order_by(SchedulerRun.finished_at.desc())
                    .first()
                )
                return row.finished_at if row else None
        except Exception as exc:
            logger.error("최근 스케줄러 성공 이력 조회 실패: %s", exc, exc_info=True)
            raise

    def finish(
        self,
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
        """실행 결과를 저장하되 기록 장애를 본 작업 실패로 전파하지 않는다."""
        if run_id is None:
            return
        failed = failed_tickers or []
        skipped = skipped_tickers or []
        try:
            with self._session_factory() as session:
                row = session.get(SchedulerRun, run_id)
                if row is None:
                    logger.error("스케줄러 실행 이력 %s을 찾을 수 없습니다.", run_id)
                    return
                row.status = status
                row.finished_at = datetime.now(UTC).replace(tzinfo=None)
                row.total_count = total_count
                row.success_count = success_count
                row.failed_count = len(failed)
                row.failed_tickers = json.dumps(failed) if failed else None
                row.skipped_count = len(skipped)
                row.skipped_tickers = json.dumps(skipped) if skipped else None
                row.publish_status = publish_status
                row.observation_count = observation_count
                row.error_message = error_message[:2000] if error_message else None
                session.commit()
        except Exception as exc:
            logger.error("스케줄러 실행 완료 이력 저장 실패: %s", exc, exc_info=True)

    def record_universe(self, run_id: int | None, universe_sha256: str) -> None:
        if run_id is None:
            return
        try:
            with self._session_factory() as session:
                row = session.get(SchedulerRun, run_id)
                if row is None:
                    return
                row.universe_sha256 = universe_sha256
                session.commit()
        except Exception as exc:
            logger.error("스케줄러 universe 계약 저장 실패: %s", exc, exc_info=True)
