import hashlib
import json
from pathlib import Path

import pytest

from herd.sec_13f_crowding_protocol_v1 import (
    Sec13fCrowdingProtocolError,
    validate_contract,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "data/herd/sec_13f_crowding_protocol_v1.json"


def _contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_protocol_locks_point_in_time_and_action_firewalls():
    contract = _contract()
    pit = contract["point_in_time_contract"]
    firewall = contract["feature_firewall"]

    assert contract["status"] == "LOCKED_BEFORE_13F_COLLECTION_AND_PRICE_OUTCOMES"
    assert pit["information_available_at"] == "EDGAR_ACCEPTANCE_DATETIME"
    assert pit["quarter_end_is_publication_time"] is False
    assert pit["manager_cik_is_issuer_cik"] is False
    assert pit["future_price_or_return_access_during_collection"] is False
    assert firewall["role"] == "SLOW_CROWDING_CONTEXT_ONLY"
    assert firewall["standalone_direction_allowed"] is False
    assert firewall["herd_weight_change_allowed"] is False
    assert contract["model_boundary"]["operational_action_ratio"] == 0.0


def test_protocol_keeps_economic_and_oos_gates_strict():
    contract = _contract()
    assert contract["collection_gates"]["minimum_history_years"] >= 10
    assert contract["collection_gates"]["minimum_non_overlapping_eras"] >= 4
    assert contract["oos_gates"]["minimum_non_overlapping_folds"] >= 4
    assert contract["oos_gates"]["minimum_incremental_roc_auc"] > 0
    assert contract["economic_gates"]["profit_take_fraction"] == 0.05
    assert contract["economic_gates"]["minimum_median_upside_capture"] >= 0.98
    assert "AUTHORIZE_ACTION_FROM_13F_ALONE" in contract["forbidden"]
    assert "OPEN_BLIND_HOLDOUT" in contract["forbidden"]


def test_protocol_prerequisite_hashes_are_current():
    for item in _contract()["pinned_prerequisites"]:
        path = ROOT / item["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]


def test_protocol_validator_emits_only_collection_authority():
    report = validate_contract()
    assert report["status"] == "PROTOCOL_LOCKED_COLLECTION_NOT_STARTED"
    assert report["next_step"] == "BUILD_OFFICIAL_13F_IMMUTABLE_CORPUS"
    assert report["price_outcomes_opened"] is False
    assert report["direction_hypothesis_executed"] is False
    assert report["operational_action_ratio"] == 0.0
    assert report["blind_holdout_access"] is False


def test_protocol_validator_rejects_quarter_end_availability(tmp_path):
    contract = _contract()
    contract["point_in_time_contract"]["quarter_end_is_publication_time"] = True
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(contract), encoding="utf-8")

    with pytest.raises(Sec13fCrowdingProtocolError):
        validate_contract(path)
