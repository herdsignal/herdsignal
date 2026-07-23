import json
from pathlib import Path

from herd.sec_auxiliary_veto_authority_v1 import audit
from herd.sec_guidance_atomic_pairs_v1 import build


ROOT = Path(__file__).resolve().parents[2]


def test_atomic_pairs_preserve_identity_and_create_no_direction() -> None:
    protocol = json.loads((ROOT / "data/herd/sec_guidance_atomic_pairs_v1.json").read_text())
    pairs, report = build(protocol)
    assert len(pairs) == report["atomic_revision_pairs"]
    assert report["direction_labels_created"] is False
    assert report["guidance_veto_authorized"] is False
    assert report["sell_authority"] is False
    assert report["herd_weight_authority"] is False


def test_sec_authority_is_veto_only_and_currently_disabled() -> None:
    protocol = json.loads((ROOT / "data/herd/sec_auxiliary_veto_authority_v1.json").read_text())
    report = audit(protocol)
    assert report["effective_sec_veto_enabled"] is False
    assert report["allowed_runtime_effects"] == []
    assert report["decision"] == "DISABLED_NO_ADMITTED_SEC_VETO"
    assert report["create_buy_authority"] is False
    assert report["create_sell_authority"] is False
    assert report["herd_weight_authority"] is False
    assert report["action_ratio_authority"] is False
