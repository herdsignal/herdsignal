import copy
import json

import pytest

from herd.sec_8k_pre_2019_identity_b001_collection_v1 import PROTOCOL, Sec8KPre2019IdentityB001CollectionV1Error, collect


def test_b001_snapshot_is_complete_and_non_promoting() -> None:
    rows, manifest = collect()
    assert len(rows) == 10
    assert sum(int(row["event_count"]) for row in rows) == 70
    assert len(manifest["files"]) == 24
    assert sum(int(row["candidate_periodic_filings"]) for row in rows) == 769
    assert manifest["metadata_is_identity_proof"] is False
    assert all(row["promotion_status"] == "BLOCKED" for row in rows)


def test_collection_rejects_metadata_as_identity_proof(tmp_path) -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8")); changed = copy.deepcopy(protocol)
    changed["authority"]["metadata_is_identity_proof"] = True
    path = tmp_path / "protocol.json"; path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(Sec8KPre2019IdentityB001CollectionV1Error, match="fail-closed"):
        collect(path)
