import copy
import json

import pytest

from herd.sec_8k_identity_extraction_failure_audit_v1 import (
    PROTOCOL,
    Sec8KIdentityFailureAuditError,
    audit,
)


def test_failure_audit_classifies_markup_false_positives() -> None:
    report = audit()

    assert report["invalid_rows"] == 10
    assert report["error_families"] == {
        "HTML_ELEMENT_NAME_CAPTURED_AS_SYMBOL": 10,
    }
    assert report["all_invalids_are_markup_tokens"] is True
    assert report["no_candidate_rows"] == 165
    assert report["recommended_parser_change"]["independent_precision_claim_allowed"] is False
    assert report["identity_promotion_allowed"] is False
    assert report["operational_action_ratio"] == 0.0


def test_failure_audit_rejects_action_authority(tmp_path) -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    changed = copy.deepcopy(protocol)
    changed["authority"]["operational_action_ratio"] = 0.05
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(Sec8KIdentityFailureAuditError, match="fail-closed"):
        audit(path)
