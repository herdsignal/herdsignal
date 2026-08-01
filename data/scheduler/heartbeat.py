"""로컬 스케줄러 생존 상태를 원자적으로 기록한다."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable


DEFAULT_HEARTBEAT_PATH = (
    Path(__file__).resolve().parents[2] / "runtime" / "scheduler-heartbeat.json"
)
SCHEMA_VERSION = "HERD_SCHEDULER_HEARTBEAT_V1"


class SchedulerHeartbeat:
    """프로세스 존재 여부 대신 최근 heartbeat 시각을 외부에 공개한다."""

    def __init__(
        self,
        path: Path = DEFAULT_HEARTBEAT_PATH,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = path
        self._now = now or (lambda: datetime.now(UTC))
        self._started_at: datetime | None = None

    def start(self) -> None:
        now = self._now()
        self._started_at = now
        self._write("RUNNING", now=now)

    def pulse(self) -> None:
        if self._started_at is None:
            self._started_at = self._now()
        self._write("RUNNING")

    def stop(self) -> None:
        if self._started_at is None:
            return
        self._write("STOPPED")

    def _write(self, status: str, *, now: datetime | None = None) -> None:
        now = now or self._now()
        started_at = self._started_at or now
        payload = {
            "schemaVersion": SCHEMA_VERSION,
            "status": status,
            "pid": os.getpid(),
            "startedAt": started_at.isoformat(),
            "lastHeartbeatAt": now.isoformat(),
            "timezone": "America/New_York",
            "schedule": "MON_THU_D1_FRI_S1_16_30_ET",
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.path)
