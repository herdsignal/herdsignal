import copy
import json

import pytest

from herd.runtime_evidence_role_mapping_v1 import (
    PROTOCOL,
    RuntimeRoleMappingError,
    audit,
)


def test_runtime_mapping_keeps_fact_status_and_private_roles_separate() -> None:
    report = audit()

    assert report["role_count"] == 10
    assert report["objective_fact_roles"] == [
        "MARKET_TAPE",
        "CHART_CROWD",
        "BUSINESS_FUNDAMENTALS",
        "MANAGEMENT_EXPECTATIONS",
    ]
    assert report["status_only_roles"] == [
        "MATERIAL_EVENTS_AND_NEWS",
        "INSIDER_BEHAVIOR",
        "SHORT_INTEREST",
        "INSTITUTIONAL_HOLDINGS",
    ]
    assert report["private_after_objective_roles"] == ["PORTFOLIO_FIT"]
    assert report["directional_vote_roles"] == 0


def test_runtime_mapping_requires_information_split_before_admission() -> None:
    report = audit()

    gaps = {row["id"]: row for row in report["runtime_gaps"]}
    assert gaps["INFORMATION_CHANGE_AREA_COLLAPSES_FOUR_SOURCE_ROLES"]["severity"] == (
        "FUTURE_SPLIT_REQUIRED"
    )
    assert report["architecture_decision"]["committee_or_agent_label_allowed"] is False
    assert report["architecture_decision"]["portfolio_sent_to_ai"] is False
    assert report["operational_action_ratio"] == 0.0


def test_runtime_mapping_rejects_action_authority(tmp_path) -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    changed = copy.deepcopy(protocol)
    changed["invariants"]["operational_action_ratio"] = 0.05
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(RuntimeRoleMappingError, match="action authority"):
        audit(path)
