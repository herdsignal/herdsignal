import json
from pathlib import Path

from herd.sec_13f_completed_cycle_gate_v1 import evaluate_gate


def _contract() -> dict:
    return {
        "required_upstream_status": "SEC_13F_DIRECTION_HYPOTHESIS_PASSED",
        "required_upstream_decision": "ALLOW_COMPLETED_5_PERCENT_CYCLE_TEST",
        "on_failure": {
            "next_step": "FINAL_REVIEW_WITH_13F_AS_NON_DIRECTIONAL_DATA_PIPELINE"
        },
    }


def test_rejected_direction_blocks_cycle_without_zero_return_claim() -> None:
    upstream = {
        "status": "SEC_13F_DIRECTION_HYPOTHESIS_REJECTED",
        "decision": "KEEP_13F_AS_NON_DIRECTIONAL_CONTEXT_ONLY",
        "gate_results": {
            "minimum_incremental_roc_auc": False,
            "minimum_evaluable_events": True,
        },
    }
    report = evaluate_gate(_contract(), upstream)
    assert report["status"] == "SEC_13F_COMPLETED_CYCLE_BLOCKED_UPSTREAM"
    assert report["cycle_executed"] is False
    assert report["cost_stress_executed"] is False
    assert report["economic_metrics"] is None
    assert "minimum_incremental_roc_auc" in report["blockers"]


def test_all_upstream_gates_only_allow_separate_economic_protocol() -> None:
    upstream = {
        "status": "SEC_13F_DIRECTION_HYPOTHESIS_PASSED",
        "decision": "ALLOW_COMPLETED_5_PERCENT_CYCLE_TEST",
        "gate_results": {"a": True, "b": True},
    }
    report = evaluate_gate(_contract(), upstream)
    assert (
        report["status"]
        == "SEC_13F_COMPLETED_CYCLE_RESEARCH_ALLOWED_NOT_EXECUTED"
    )
    assert report["cycle_executed"] is False


def test_contract_blocks_all_economic_and_operational_paths() -> None:
    contract = json.loads(
        (
            Path(__file__).parents[1]
            / "herd/sec_13f_completed_cycle_gate_v1.json"
        ).read_text(encoding="utf-8")
    )
    blocked = set(contract["blocked_operations"])
    assert "EXECUTE_5_PERCENT_PROFIT_TAKE" in blocked
    assert "RUN_100_BPS_ROUND_TRIP_COST" in blocked
    assert "ENABLE_OPERATIONAL_ACTION_RATIO" in blocked
    assert "OPEN_BLIND_HOLDOUT" in blocked
