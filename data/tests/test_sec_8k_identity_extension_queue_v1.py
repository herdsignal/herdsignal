import copy
import csv
import json

import pytest

from herd.sec_8k_identity_extension_queue_v1 import (
    PROTOCOL_PATH,
    Sec8KIdentityQueueError,
    build,
)


def _protocol() -> dict:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def test_queue_covers_every_unresolved_event() -> None:
    rows, report = build(_protocol())
    assert len(rows) == 762
    assert len({row["event_id"] for row in rows}) == 762
    assert report["price_outcomes_opened"] is False
    assert report["direction_hypothesis_allowed"] is False
    assert report["operational_action_ratio"] == 0.0


def test_queue_uses_only_sec_primary_documents() -> None:
    rows, _ = build(_protocol())
    assert all(row["primary_document_url"].startswith("https://www.sec.gov/") for row in rows)
    assert all(row["collection_status"] == "PENDING" for row in rows)
    assert all(row["adjudication_status"] == "PENDING" for row in rows)


def test_action_authority_cannot_be_enabled() -> None:
    protocol = copy.deepcopy(_protocol())
    protocol["authority"]["operational_action_ratio"] = 0.05
    with pytest.raises(Sec8KIdentityQueueError):
        build(protocol)


def test_written_queue_matches_builder() -> None:
    rows, _ = build(_protocol())
    with open(
        "data/reports/sec_8k_identity_extension_queue_v1.csv",
        newline="",
        encoding="utf-8",
    ) as handle:
        persisted = list(csv.DictReader(handle))
    assert persisted == rows
