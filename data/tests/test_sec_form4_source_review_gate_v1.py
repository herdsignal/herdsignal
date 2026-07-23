import json

import pandas as pd

from herd.sec_form4_source_review_gate_v1 import evaluate


def _protocol(path, minimum=2):
    path.write_text(json.dumps({
        "status": "LOCKED_BEFORE_ACCESSION_CATALOG",
        "forbidden": [
            "USE_PRICE_OUTCOMES", "TREAT_ALL_SALES_AS_BEARISH", "DROP_FOOTNOTES",
        ],
        "source_review_gate": {
            "minimum_reviewed_transactions": minimum,
            "minimum_distinct_issuers": 2,
            "minimum_transaction_code_coverage": 0.98,
            "minimum_required_field_accuracy": 0.95,
            "minimum_wilson_95_lower_bound": 0.0,
            "labels": ["VALID", "INVALID", "AMBIGUOUS"],
        },
    }))


def test_pending_review_never_passes(tmp_path):
    review = tmp_path / "review.csv"
    atomic = tmp_path / "atomic.csv"
    protocol = tmp_path / "protocol.json"
    _protocol(protocol)
    pd.DataFrame([
        {"issuerCik": "1", "transactionCode": "P", "reviewDecision": "PENDING"},
        {"issuerCik": "2", "transactionCode": "S", "reviewDecision": "VALID"},
    ]).to_csv(review, index=False)
    pd.DataFrame([
        {"transactionCode": "P"}, {"transactionCode": "S"},
    ]).to_csv(atomic, index=False)
    result = evaluate(review, atomic, protocol)
    assert result["status"] == "SOURCE_REVIEW_PENDING"
    assert result["accuracy_gate_passed"] is False
    assert result["direction_hypothesis_allowed"] is False


def test_complete_accurate_review_can_pass_without_action_authority(tmp_path):
    review = tmp_path / "review.csv"
    atomic = tmp_path / "atomic.csv"
    protocol = tmp_path / "protocol.json"
    _protocol(protocol)
    pd.DataFrame([
        {"issuerCik": "1", "transactionCode": "P", "reviewDecision": "VALID"},
        {"issuerCik": "2", "transactionCode": "S", "reviewDecision": "VALID"},
    ]).to_csv(review, index=False)
    pd.DataFrame([
        {"transactionCode": "P"}, {"transactionCode": "S"},
    ]).to_csv(atomic, index=False)
    result = evaluate(review, atomic, protocol)
    assert result["accuracy_gate_passed"] is True
    assert result["operational_action_authority"] is False
