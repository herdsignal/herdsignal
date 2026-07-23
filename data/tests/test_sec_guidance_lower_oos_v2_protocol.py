import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "data/herd/sec_guidance_lower_oos_v2.json"


def test_protocol_is_locked_before_price_outcome_join():
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["status"] == "PREREGISTERED_BEFORE_PRICE_OUTCOME_JOIN"
    assert protocol["economic_hypothesis"]["treatment"] == "midpoint_delta < 0"
    assert protocol["adoption_gate"]["all_required"] is True
    assert protocol["claim_boundary"]["operational_action_ratio"] == 0.0
    assert protocol["claim_boundary"]["blind_holdout_access"] is False
    assert "COUNT_ROWS_AS_INDEPENDENT_OBSERVATIONS" in protocol["forbidden"]


def test_all_locked_input_hashes_match():
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    for artifact in protocol["locked_inputs"].values():
        path = ROOT / artifact["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
