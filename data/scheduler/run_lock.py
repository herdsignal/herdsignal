"""단일 호스트에서 Tier1 중복 실행을 막는 비차단 파일 잠금."""

from __future__ import annotations

import fcntl
from pathlib import Path
from typing import TextIO


class SchedulerRunLock:
    def __init__(self, handle: TextIO):
        self._handle = handle

    @classmethod
    def try_acquire(cls, path: Path) -> "SchedulerRunLock | None":
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            return None
        return cls(handle)

    def release(self) -> None:
        fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        self._handle.close()
