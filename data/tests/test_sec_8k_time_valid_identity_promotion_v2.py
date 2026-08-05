import copy
import json

import pytest

from herd.sec_8k_time_valid_identity_promotion_v2 import (
    PROTOCOL, Sec8KIdentityPromotionV2Error, build,
)


def test_promotion_uses_only_reviewed_event_date_identities() -> None:
    rows, report = build()
    assert len(rows) == 115
    assert report["open_ended_intervals_inferred"] == 0
    assert all(row["identity_scope"] == "EXACT_FILING_DATE_EVENT_ONLY" for row in rows)
    assert report["operational_action_ratio"] == 0.0


def test_promotion_rejects_open_ended_interval_authority(tmp_path) -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    changed = copy.deepcopy(protocol)
    changed["promotion"]["infer_open_ended_ticker_interval"] = True
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(Sec8KIdentityPromotionV2Error, match="fail-closed"):
        build(path)
