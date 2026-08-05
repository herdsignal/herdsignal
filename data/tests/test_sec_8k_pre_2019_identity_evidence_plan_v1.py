import copy
import json

import pytest

from herd.sec_8k_pre_2019_identity_evidence_plan_v1 import PROTOCOL, Sec8KPre2019IdentityEvidencePlanV1Error, build


def test_pre_2019_events_are_bounded_as_issuer_work() -> None:
    rows, report = build()
    assert len(rows) == 198
    assert sum(int(row["event_count"]) for row in rows) == 646
    assert report["issuers_with_reviewed_anchor"] == 78
    assert report["issuers_without_reviewed_anchor"] == 120
    assert report["batch_count"] == 20
    assert all(row["promotion_status"] == "BLOCKED" for row in rows)
    assert report["operational_action_ratio"] == 0.0


def test_plan_rejects_automatic_promotion(tmp_path) -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8")); changed = copy.deepcopy(protocol)
    changed["authority"]["automatic_identity_promotion"] = True
    path = tmp_path / "protocol.json"; path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(Sec8KPre2019IdentityEvidencePlanV1Error, match="fail-closed"):
        build(path)
