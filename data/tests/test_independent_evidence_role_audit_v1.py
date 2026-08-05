import copy
import json

import pytest

from herd.independent_evidence_role_audit_v1 import (
    PROTOCOL,
    EvidenceRoleAuditError,
    audit,
)


def test_role_audit_keeps_all_roles_non_directional() -> None:
    report = audit()

    assert report["summary"]["role_count"] == 10
    assert report["summary"]["directional_vote_roles"] == 0
    assert report["summary"]["price_domain_roles"] == [
        "MARKET_TAPE",
        "CHART_CROWD",
    ]
    assert report["summary"]["price_domain_vote_count"] == 0
    assert report["architecture_decision"]["majority_vote_allowed"] is False
    assert report["architecture_decision"]["call_roles_ai_agents"] is False
    assert report["operational_action_ratio"] == 0.0


def test_role_audit_exposes_real_information_gaps() -> None:
    report = audit()
    roles = {row["id"]: row for row in report["roles"]}

    assert roles["MATERIAL_EVENTS_AND_NEWS"]["coverage"] == {
        "sec_8k_candidates": 110,
        "sec_8k_reviewed": 110,
        "pit_news_connected": False,
    }
    assert roles["MANAGEMENT_EXPECTATIONS"]["coverage"]["valid_atomic_facts"] == 700
    assert roles["SHORT_INTEREST"]["coverage"]["settlement_dates"] == 122
    assert roles["INSTITUTIONAL_HOLDINGS"]["directional_vote"] is False


def test_role_audit_rejects_action_authority(tmp_path) -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    changed = copy.deepcopy(protocol)
    changed["authority"]["operational_action_ratio"] = 0.05
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(EvidenceRoleAuditError, match="action authority"):
        audit(path)
