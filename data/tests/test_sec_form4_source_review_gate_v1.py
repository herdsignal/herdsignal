import json

import pandas as pd

from herd.sec_form4_source_review_gate_v1 import evaluate


def _protocol(path, minimum=2):
    path.write_text(json.dumps({
        "status": "LOCKED_BEFORE_HUMAN_SOURCE_REVIEW",
        "gate": {
            "minimum_reviewed_transactions": minimum,
            "minimum_distinct_issuers": 2,
            "minimum_transaction_code_volume_coverage": 0.98,
            "minimum_required_field_accuracy": 0.95,
            "minimum_wilson_95_lower_bound": 0.0,
        },
        "decision_rules": {
            "VALID": "", "INVALID": "", "AMBIGUOUS": "", "PENDING": "",
        }
    }))


def _structural(path, count=2, status="STRUCTURAL_AUDIT_PASSED"):
    path.write_text(json.dumps({"status": status, "transactions": count}))


def test_pending_review_never_passes(tmp_path):
    review = tmp_path / "review.csv"
    atomic = tmp_path / "atomic.csv"
    protocol = tmp_path / "protocol.json"
    structural = tmp_path / "structural.json"
    _protocol(protocol)
    _structural(structural)
    pd.DataFrame([
        {"issuerCik": "1", "transactionCode": "P", "reviewDecision": "PENDING"},
        {"issuerCik": "2", "transactionCode": "S", "reviewDecision": "VALID"},
    ]).to_csv(review, index=False)
    pd.DataFrame([
        {"transactionCode": "P"}, {"transactionCode": "S"},
    ]).to_csv(atomic, index=False)
    result = evaluate(review, atomic, protocol, structural)
    assert result["status"] == "SOURCE_REVIEW_PENDING"
    assert result["accuracy_gate_passed"] is False
    assert result["direction_hypothesis_allowed"] is False


def test_complete_accurate_review_can_pass_without_action_authority(tmp_path):
    review = tmp_path / "review.csv"
    atomic = tmp_path / "atomic.csv"
    protocol = tmp_path / "protocol.json"
    structural = tmp_path / "structural.json"
    _protocol(protocol)
    _structural(structural)
    pd.DataFrame([
        {"issuerCik": "1", "transactionCode": "P", "reviewDecision": "VALID"},
        {"issuerCik": "2", "transactionCode": "S", "reviewDecision": "VALID"},
    ]).to_csv(review, index=False)
    pd.DataFrame([
        {"transactionCode": "P"}, {"transactionCode": "S"},
    ]).to_csv(atomic, index=False)
    result = evaluate(review, atomic, protocol, structural)
    assert result["accuracy_gate_passed"] is True
    assert result["operational_action_authority"] is False
