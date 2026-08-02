"""Hash-chained JSONL ledger used by prospective research intake."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable


class AppendOnlyLedgerError(RuntimeError):
    """Raised when an immutable ledger is malformed or conflicts with new data."""


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def read_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    previous_hash = "GENESIS"
    with path.open(encoding="utf-8") as stream:
        for line_number, raw in enumerate(stream, start=1):
            if not raw.strip():
                raise AppendOnlyLedgerError(f"blank ledger line: {line_number}")
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise AppendOnlyLedgerError(
                    f"invalid ledger JSON at line {line_number}"
                ) from exc
            expected = {
                "sequence", "previous_hash", "payload", "payload_hash", "record_hash"
            }
            if set(row) != expected or row["sequence"] != line_number:
                raise AppendOnlyLedgerError(f"invalid ledger envelope: {line_number}")
            if row["previous_hash"] != previous_hash:
                raise AppendOnlyLedgerError(f"broken hash chain: {line_number}")
            if row["payload_hash"] != _digest(row["payload"]):
                raise AppendOnlyLedgerError(f"payload hash mismatch: {line_number}")
            record_material = {
                "sequence": row["sequence"],
                "previous_hash": row["previous_hash"],
                "payload_hash": row["payload_hash"],
            }
            if row["record_hash"] != _digest(record_material):
                raise AppendOnlyLedgerError(f"record hash mismatch: {line_number}")
            previous_hash = row["record_hash"]
            rows.append(row)
    return rows


def append_unique(
    path: Path,
    payloads: Iterable[dict[str, Any]],
    *,
    identity_field: str,
) -> dict[str, int]:
    """Append unseen payloads and reject conflicting reuse of an identity."""
    candidates = list(payloads)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        rows = read_ledger(path)
        known = {
            str(row["payload"][identity_field]): row["payload_hash"] for row in rows
        }
        appended = 0
        duplicates = 0
        previous_hash = rows[-1]["record_hash"] if rows else "GENESIS"
        with path.open("a", encoding="utf-8") as stream:
            for payload in candidates:
                if identity_field not in payload or not str(payload[identity_field]).strip():
                    raise AppendOnlyLedgerError(
                        f"missing ledger identity: {identity_field}"
                    )
                identity = str(payload[identity_field])
                payload_hash = _digest(payload)
                if identity in known:
                    if known[identity] != payload_hash:
                        raise AppendOnlyLedgerError(
                            f"conflicting immutable identity: {identity}"
                        )
                    duplicates += 1
                    continue
                sequence = len(rows) + appended + 1
                material = {
                    "sequence": sequence,
                    "previous_hash": previous_hash,
                    "payload_hash": payload_hash,
                }
                record_hash = _digest(material)
                envelope = {
                    **material,
                    "payload": payload,
                    "record_hash": record_hash,
                }
                stream.write(_canonical(envelope).decode("utf-8") + "\n")
                stream.flush()
                os.fsync(stream.fileno())
                known[identity] = payload_hash
                previous_hash = record_hash
                appended += 1
        return {"appended": appended, "duplicates": duplicates, "total": len(known)}
