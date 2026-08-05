import copy
import json

import pytest

from herd.sec_8k_remaining_identity_coverage_audit_v2 import (
    PROTOCOL,
    Sec8KRemainingIdentityCoverageAuditV2Error,
    build,
)


def test_all_remaining_gaps_are_routed_without_identity_inference() -> None:
    rows, report = build()
    assert len(rows) == 647
    assert report["legacy_events"] == 646
    assert report["legacy_with_same_cik_anchor"] == 343
    assert report["legacy_without_same_cik_anchor"] == 303
    assert report["modern_without_candidate"] == 1
    assert report["same_cik_anchor_implies_interval"] is False
    assert report["operational_action_ratio"] == 0.0


def test_audit_rejects_current_ticker_backfill_authority(tmp_path) -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    changed = copy.deepcopy(protocol)
    changed["authority"]["current_ticker_backfill_allowed"] = True
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(Sec8KRemainingIdentityCoverageAuditV2Error, match="fail-closed"):
        build(path)
