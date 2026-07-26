"""스케줄러 결과를 프로세스 밖에서 감사 가능한 원자 JSON 사건으로 남긴다."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

SCHEMA_VERSION = "HERD_OPERATION_EVENT_V1"


def write_operation_event(
    result: dict[str, Any],
    *,
    output_dir: Path,
    now: datetime | None = None,
) -> Path:
    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    event = {
        "schemaVersion": SCHEMA_VERSION,
        "recordedAt": timestamp.isoformat().replace("+00:00", "Z"),
        "result": result,
    }
    canonical = json.dumps(
        event,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    envelope = {
        **event,
        "contentSha256": hashlib.sha256(canonical).hexdigest(),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    name = f"{timestamp:%Y%m%dT%H%M%S.%fZ}-{uuid4().hex[:8]}.json"
    target = output_dir / name
    temporary = target.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(envelope, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, target)
    return target
