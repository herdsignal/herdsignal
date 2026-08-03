import copy
import json

import pytest

from herd.role_specific_source_gap_priority_v1 import (
    PROTOCOL,
    SourceGapPriorityError,
    audit,
)


def test_source_gap_priority_selects_one_bounded_next_part() -> None:
    report = audit()
    decisions = {row["source"]: row for row in report["decisions"]}

    assert report["summary"] == {
        "direction_ready_sources": 0,
        "bounded_manual_review_sources": 1,
        "prospective_collection_only_sources": 1,
        "deferred_sources": 1,
        "stopped_direction_sources": 2,
    }
    assert decisions["SEC_MATERIAL_EVENT"]["coverage"] == {
        "candidate_rows": 110,
        "reviewed_rows": 10,
        "pending_rows": 100,
    }
    assert decisions["FINRA_SHORT_INTEREST"]["decision"] == "CONTINUE_APPEND_ONLY_SHADOW"
    assert decisions["POINT_IN_TIME_NEWS"]["decision"] == (
        "DEFER_UNTIL_SOURCE_RIGHTS_AND_VERSION_CONTRACT"
    )
    assert report["selected_next_part"]["id"] == "SEC_8K_MATERIAL_EVENT_REVIEW_BATCHING"


def test_rejected_sources_remain_non_directional() -> None:
    report = audit()
    decisions = {row["source"]: row for row in report["decisions"]}

    assert decisions["SEC_FORM4"]["decision"].startswith("STOP_DIRECTION_RESEARCH")
    assert decisions["SEC_13F"]["decision"].startswith("STOP_DIRECTION_RESEARCH")
    assert all(row["direction_vote"] is False for row in report["decisions"])
    assert report["new_hypothesis_allowed"] is False
    assert report["operational_action_ratio"] == 0.0


def test_source_gap_priority_rejects_action_authority(tmp_path) -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    changed = copy.deepcopy(protocol)
    changed["authority"]["operational_action_ratio"] = 0.05
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(SourceGapPriorityError, match="authorize an action"):
        audit(path)
