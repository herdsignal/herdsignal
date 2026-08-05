import copy
import json

import pytest

from herd.sec_8k_structural_evaluation_collection_v1 import (
    PROTOCOL,
    Sec8KStructuralEvaluationCollectionError,
    select_queue,
)


def test_collection_queue_is_sec_only_and_label_blind() -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    rows = select_queue(protocol)

    assert len(rows) == 185
    assert all(row["primary_document_url"].startswith("https://www.sec.gov/") for row in rows)
    assert all("canonical_symbol" not in row for row in rows)


def test_collection_rejects_action_authority(tmp_path) -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    changed = copy.deepcopy(protocol)
    changed["authority"]["operational_action_ratio"] = 0.05
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(Sec8KStructuralEvaluationCollectionError, match="fail-closed"):
        select_queue(changed)
