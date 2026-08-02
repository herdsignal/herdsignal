from __future__ import annotations

import json

import pytest

from herd.append_only_ledger import (
    AppendOnlyLedgerError,
    append_unique,
    read_ledger,
)


def test_append_only_ledger_is_idempotent_and_hash_chained(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    payloads = [{"event_id": "E1", "value": 1}, {"event_id": "E2", "value": 2}]
    assert append_unique(path, payloads, identity_field="event_id")["appended"] == 2
    assert append_unique(path, payloads, identity_field="event_id")["duplicates"] == 2
    rows = read_ledger(path)
    assert [row["sequence"] for row in rows] == [1, 2]
    assert rows[1]["previous_hash"] == rows[0]["record_hash"]


def test_append_only_ledger_rejects_identity_rewrite(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    append_unique(path, [{"event_id": "E1", "value": 1}], identity_field="event_id")
    with pytest.raises(AppendOnlyLedgerError, match="conflicting"):
        append_unique(path, [{"event_id": "E1", "value": 9}], identity_field="event_id")


def test_append_only_ledger_detects_manual_tampering(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    append_unique(path, [{"event_id": "E1", "value": 1}], identity_field="event_id")
    row = json.loads(path.read_text())
    row["payload"]["value"] = 3
    path.write_text(json.dumps(row) + "\n")
    with pytest.raises(AppendOnlyLedgerError, match="payload hash"):
        read_ledger(path)
