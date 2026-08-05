import copy
import csv
import json

import pytest

from herd.sec_8k_identity_source_review_v1 import PROTOCOL_PATH as SOURCE_PROTOCOL
from herd.sec_8k_material_event_review_batching_v1 import (
    PROTOCOL,
    Sec8KReviewBatchingError,
    build_plan,
    build_worklist,
)


def _inputs():
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    source_protocol = json.loads(SOURCE_PROTOCOL.read_text(encoding="utf-8"))
    with open(protocol["source_review_labels"], newline="", encoding="utf-8") as handle:
        labels = list(csv.DictReader(handle))
    return protocol, source_protocol, labels


def test_batch_plan_covers_every_review_once_without_auto_labels() -> None:
    protocol, source_protocol, labels = _inputs()
    for row in labels:
        row["decision"] = "PENDING"
        row["approved_symbol"] = ""
        row["review_note"] = ""
    plan, report = build_plan(protocol, source_protocol, labels)

    assert len(plan) == 110
    assert len({row["review_id"] for row in plan}) == 110
    assert report["batch_count"] == 11
    assert all(row["rows"] == 10 for row in report["batches"])
    assert report["next_pending_batch"] == "B001"
    assert report["auto_labels_created"] == 0
    assert report["plan_is_read_only_projection"] is True
    assert report["identity_promotion_allowed"] is False


def test_reviewed_first_batch_resumes_at_second_batch() -> None:
    protocol, source_protocol, labels = _inputs()
    for row in labels:
        row["decision"] = "PENDING"
        row["approved_symbol"] = ""
        row["review_note"] = ""
    for row in labels[:10]:
        row["decision"] = "INVALID"
        row["review_note"] = "source checked"
    _, report = build_plan(protocol, source_protocol, labels)

    assert report["batches"][0]["complete"] is True
    assert report["next_pending_batch"] == "B002"


def test_batching_rejects_action_authority() -> None:
    protocol, source_protocol, labels = _inputs()
    changed = copy.deepcopy(protocol)
    changed["authority"]["operational_action_ratio"] = 0.05

    with pytest.raises(Sec8KReviewBatchingError, match="authorize an action"):
        build_plan(changed, source_protocol, labels)


def test_worklist_exposes_sources_without_creating_labels() -> None:
    protocol, source_protocol, labels = _inputs()
    plan, _ = build_plan(protocol, source_protocol, labels)

    worklist = build_worklist(plan, "B005")

    assert worklist["rows"] == 10
    assert worklist["pending"] == 10
    assert worklist["read_only"] is True
    assert worklist["items"][0]["review_id"].startswith("REVIEW-")
    assert worklist["items"][0]["source_url"].startswith("https://www.sec.gov/")
    assert len(worklist["items"][0]["source_sha256"]) == 64


def test_worklist_rejects_unknown_batch() -> None:
    protocol, source_protocol, labels = _inputs()
    plan, _ = build_plan(protocol, source_protocol, labels)

    with pytest.raises(Sec8KReviewBatchingError, match="unknown batch"):
        build_worklist(plan, "B999")
