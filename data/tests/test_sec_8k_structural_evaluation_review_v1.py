import copy
import json

import pytest

from herd.sec_8k_structural_evaluation_review_v1 import (
    PROTOCOL,
    Sec8KStructuralEvaluationReviewError,
    evaluate,
    expected_rows,
    record_explicit_decisions,
)


def test_review_builds_nineteen_batches_without_labels() -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    plan, report = evaluate(protocol, expected_rows(protocol))

    assert len(plan) == 182
    assert report["batch_count"] == 19
    assert report["batches"][-1]["rows"] == 2
    assert report["next_pending_batch"] == "B001"
    assert report["known_identity_labels_used"] == 0
    assert report["identity_promotion_allowed"] is False


def test_review_rejects_known_identity_authority(tmp_path) -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    changed = copy.deepcopy(protocol)
    changed["review_scope"]["known_identity_labels_allowed"] = True
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(Sec8KStructuralEvaluationReviewError, match="fail-closed"):
        evaluate(changed, expected_rows(protocol))


def test_explicit_review_rejects_overwrite() -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    rows = expected_rows(protocol)
    with pytest.raises(
        Sec8KStructuralEvaluationReviewError, match="overwrite"
    ):
        record_explicit_decisions(protocol, [{
            "review_id": rows[10]["review_id"],
            "approved_symbol": "NOPE",
            "review_note": "source checked",
        }])
