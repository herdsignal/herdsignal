import copy
import json

import pytest

from herd.sec_8k_identity_source_review_v1 import (
    PROTOCOL_PATH,
    Sec8KIdentitySourceReviewError,
    build_review_rows,
    evaluate,
)


def _protocol() -> dict:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def test_initial_review_is_pending_and_promotes_nothing() -> None:
    protocol = _protocol()
    rows = build_review_rows(protocol)
    report = evaluate(protocol, rows)
    assert len(rows) == 110
    assert report["status"] == "PENDING_SOURCE_DECISIONS"
    assert report["approved_identity_rows"] == 0
    assert report["identity_promotion_allowed"] is False
    assert report["operational_action_ratio"] == 0.0


def test_valid_decision_requires_source_candidate() -> None:
    protocol = _protocol()
    rows = build_review_rows(protocol)
    rows[0]["decision"] = "VALID"
    rows[0]["approved_symbol"] = "NOT_IN_SOURCE"
    with pytest.raises(Sec8KIdentitySourceReviewError):
        evaluate(protocol, rows)


def test_source_fields_are_immutable() -> None:
    protocol = _protocol()
    rows = build_review_rows(protocol)
    rows[0]["source_sha256"] = "0" * 64
    with pytest.raises(Sec8KIdentitySourceReviewError):
        evaluate(protocol, rows)


def test_action_authority_cannot_be_enabled() -> None:
    protocol = copy.deepcopy(_protocol())
    protocol["authority"]["operational_action_ratio"] = 0.05
    with pytest.raises(Sec8KIdentitySourceReviewError):
        evaluate(protocol, build_review_rows(_protocol()))


def test_completed_review_that_misses_precision_gate_stops_promotion() -> None:
    protocol = _protocol()
    rows = build_review_rows(protocol)
    for index, row in enumerate(rows):
        row["decision"] = "VALID" if index < 100 else "INVALID"
        row["approved_symbol"] = row["candidate_symbols"].split("|")[0] if index < 100 else ""
        row["review_note"] = "source checked"

    report = evaluate(protocol, rows)

    assert report["status"] == "SOURCE_PRECISION_GATE_FAILED"
    assert report["identity_promotion_allowed"] is False
    assert report["next_stage"] == "STOP_SEC_8K_IDENTITY_PROMOTION_SOURCE_PRECISION_FAILED"
