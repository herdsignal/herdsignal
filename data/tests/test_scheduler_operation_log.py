import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from scheduler.operation_log import write_operation_event


def test_writes_hashed_atomic_operation_event(tmp_path: Path) -> None:
    result = {
        "status": "SUCCESS",
        "total": 2,
        "success": ["AAPL", "SPY"],
        "failed": [],
    }
    target = write_operation_event(
        result,
        output_dir=tmp_path,
        now=datetime(2026, 7, 26, 21, 30, tzinfo=UTC),
    )

    payload = json.loads(target.read_text(encoding="utf-8"))
    digest = payload.pop("contentSha256")
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    assert digest == hashlib.sha256(canonical).hexdigest()
    assert payload["result"] == result
    assert not list(tmp_path.glob("*.tmp"))
