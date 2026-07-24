from copy import deepcopy

from herd.sec_13f_phase_review_v1 import review_payload


INPUTS = [
    ("raw", "OFFICIAL_13F_RAW_CORPUS_HASH_LOCKED"),
    ("security", "SECURITY_IDENTIFIER_LEDGER_GATE_PASSED"),
    ("pit", "CONSERVATIVE_PIT_HOLDINGS_LEDGER_GATE_PASSED"),
    ("review", "STRATIFIED_SEC_SOURCE_REVIEW_GATE_PASSED"),
    ("context", "SEC_13F_SLOW_CONTEXT_GATE_PASSED"),
    (
        "data/reports/sec_13f_crowding_incremental_oos_v1.json",
        "SEC_13F_DIRECTION_HYPOTHESIS_REJECTED",
    ),
    (
        "data/reports/sec_13f_completed_cycle_gate_v1.json",
        "SEC_13F_COMPLETED_CYCLE_BLOCKED_UPSTREAM",
    ),
]


def _fixtures() -> tuple[dict, dict]:
    contract = {
        "pinned_inputs": [
            {"path": path, "required_status": status}
            for path, status in INPUTS
        ],
        "required_firewall": {
            "operational_action_ratio": 0.0,
            "blind_holdout_access": False,
            "direction_decision": "KEEP_13F_AS_NON_DIRECTIONAL_CONTEXT_ONLY",
            "cycle_executed": False,
            "economic_metrics": None,
        },
    }
    reports = {
        path: {
            "status": status,
            "operational_action_ratio": 0.0,
            "blind_holdout_access": False,
        }
        for path, status in INPUTS
    }
    direction = reports[
        "data/reports/sec_13f_crowding_incremental_oos_v1.json"
    ]
    direction.update(
        {
            "decision": "KEEP_13F_AS_NON_DIRECTIONAL_CONTEXT_ONLY",
            "gate_results": {"coverage": True, "direction": False},
            "aggregate_metrics": {
                "incremental_roc_auc": 0.01,
                "candidate_minus_baseline_log_loss": 0.001,
            },
        }
    )
    reports[
        "data/reports/sec_13f_completed_cycle_gate_v1.json"
    ].update({"cycle_executed": False, "economic_metrics": None})
    return contract, reports


def test_rejected_direction_can_complete_review_without_action_authority() -> None:
    contract, reports = _fixtures()
    review = review_payload(contract, reports)
    assert (
        review["status"]
        == "SEC_13F_PHASE_REVIEW_PASSED_WITH_DIRECTION_REJECTED"
    )
    assert review["final_scope"]["completed_cycle_allowed"] is False
    assert review["final_scope"]["operational_action_ratio"] == 0.0


def test_review_fails_closed_if_any_stage_opens_operational_action() -> None:
    contract, reports = _fixtures()
    changed = deepcopy(reports)
    changed["context"]["operational_action_ratio"] = 0.05
    review = review_payload(contract, changed)
    assert review["status"] == "SEC_13F_PHASE_REVIEW_FAILED"
    assert review["research_firewall_checks"]["all_action_ratios_zero"] is False
