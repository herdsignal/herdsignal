import json
from pathlib import Path

import pytest

from herd.overnight_pit_shadow_runner_v1 import (
    CONTRACT,
    OvernightExpansionError,
    RunStateStore,
    load_and_verify_contract,
    preflight,
    sha256,
)


ROOT = Path(__file__).resolve().parents[2]


def test_overnight_contract_is_locked_with_closed_authority():
    contract = load_and_verify_contract()
    assert contract["research_tier"] == "PUBLIC_RESEARCH_ONLY"
    assert len(contract["stages"]) == 7
    assert contract["authority"]["price_outcomes_opened"] is False
    assert contract["authority"]["future_return_labels_allowed"] is False
    assert contract["authority"]["herd_formula_change_allowed"] is False
    assert contract["authority"]["blind_holdout_access"] is False
    assert contract["authority"]["operational_action_ratio"] == 0.0


def test_volume_target_never_overrides_source_exhaustion_gate():
    semantics = load_and_verify_contract()["completion_semantics"]
    assert semantics["numeric_volume_is_estimate_only"] is True
    assert semantics["stage_completes_on_eligible_source_exhaustion"] is True
    assert semantics["later_stage_must_not_start_while_current_stage_gate_fails"]


def test_sec_request_policy_stays_below_official_limit():
    policy = load_and_verify_contract()["source_policy"]["sec"]
    assert policy["user_agent_required"] is True
    assert policy["requests_per_second"] == 3.0
    assert policy["requests_per_second"] <= 10.0
    assert 429 in policy["retry_statuses"]
    assert policy["maximum_backoff_seconds"] <= 60.0


def test_locked_input_hashes_match_repository():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    for locked in contract["locked_inputs"]:
        assert sha256(ROOT / locked["path"]) == locked["sha256"]


def test_state_is_atomic_resumable_and_ordered(tmp_path):
    store = RunStateStore(tmp_path / "state.json")
    first = store.initialize()
    resumed = store.initialize()
    assert resumed["contract_sha256"] == first["contract_sha256"]
    assert not list(tmp_path.glob("*.tmp"))

    with pytest.raises(OvernightExpansionError):
        store.complete_stage("PART_2", 1, "b" * 64)

    store.record_item("PART_1", "contract")
    store.record_item("PART_1", "contract")
    state = store.complete_stage("PART_1", 1, "a" * 64)
    assert state["last_completed_stage"] == "PART_1"
    assert state["stages"]["PART_1"]["status"] == "COMPLETE"
    assert state["stages"]["PART_1"]["completed_item_ids"] == ["contract"]


def test_unresolved_failures_block_stage_completion(tmp_path):
    store = RunStateStore(tmp_path / "state.json")
    store.initialize()
    store.record_item("PART_1", "sample", error="temporary failure")
    with pytest.raises(OvernightExpansionError):
        store.complete_stage("PART_1", 0, "a" * 64)
    state = store.record_item("PART_1", "sample")
    assert state["stages"]["PART_1"]["failed_items"] == []
    assert state["stages"]["PART_1"]["completed_item_ids"] == ["sample"]


def test_preflight_creates_safe_checkpoint(tmp_path):
    result = preflight(state_path=tmp_path / "state.json")
    assert result["status"] == "PREFLIGHT_PASS"
    assert result["free_disk_bytes"] >= result["minimum_free_disk_bytes"]
    assert result["price_outcomes_opened"] is False
    assert result["operational_action_ratio"] == 0.0
