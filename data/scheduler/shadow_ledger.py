"""승격 전 shadow 관찰을 행동 권한 없이 해시 체인으로 기록한다."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

GENESIS_HASH = "0" * 64
SCHEMA_VERSION = "HERD_SHADOW_LEDGER_V1"
FORBIDDEN_OUTPUT_KEYS = {"action", "actionRatio", "targetWeight", "buy", "sell"}


class ShadowLedgerError(ValueError):
    pass


def _hash(record: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def verify_shadow_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    previous = GENESIS_HASH
    for index, envelope in enumerate(rows, start=1):
        record_hash = envelope.get("recordHash")
        record = {key: value for key, value in envelope.items() if key != "recordHash"}
        if record.get("previousHash") != previous or record_hash != _hash(record):
            raise ShadowLedgerError(f"shadow 원장 해시 체인 불일치: line {index}")
        previous = record_hash
    return rows


def append_shadow_observation(
    path: Path,
    *,
    candidate_id: str,
    observed_at: datetime,
    as_of_date: date,
    ticker: str,
    input_sha256: str,
    output: dict[str, Any],
) -> dict[str, Any]:
    if not candidate_id.strip():
        raise ShadowLedgerError("candidate_id가 필요합니다.")
    forbidden = FORBIDDEN_OUTPUT_KEYS.intersection(output)
    if forbidden:
        raise ShadowLedgerError(
            f"shadow 원장에는 행동 출력을 기록할 수 없습니다: {sorted(forbidden)}"
        )
    if len(input_sha256) != 64:
        raise ShadowLedgerError("input_sha256 형식이 올바르지 않습니다.")

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            handle.seek(0)
            existing = verify_shadow_ledger(path)
            previous = existing[-1]["recordHash"] if existing else GENESIS_HASH
            record = {
                "schemaVersion": SCHEMA_VERSION,
                "candidateId": candidate_id.strip(),
                "observedAt": observed_at.isoformat(),
                "asOfDate": as_of_date.isoformat(),
                "ticker": ticker.strip().upper(),
                "inputSha256": input_sha256,
                "output": output,
                "previousHash": previous,
            }
            envelope = {**record, "recordHash": _hash(record)}
            handle.seek(0, os.SEEK_END)
            handle.write(json.dumps(envelope, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            return envelope
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
