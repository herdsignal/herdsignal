import copy
import json

import pytest

from herd.sec_8k_structural_evaluation_extraction_v1 import (
    PROTOCOL,
    Sec8KStructuralEvaluationExtractionError,
    build,
)


def test_independent_extraction_uses_frozen_parser_without_labels() -> None:
    rows, report = build()

    assert len(rows) == 185
    assert report["parser_changed_after_lock"] is False
    assert report["human_labels_created"] == 0
    assert report["identity_promotion_allowed"] is False
    assert report["operational_action_ratio"] == 0.0
    assert all(row["review_status"] in {"PENDING", "NO_CANDIDATE"} for row in rows)


def test_independent_extraction_rejects_parser_changes(tmp_path) -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    changed = copy.deepcopy(protocol)
    changed["parser"]["code_changes_allowed_after_lock"] = True
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(Sec8KStructuralEvaluationExtractionError, match="fail-closed"):
        build(path)
