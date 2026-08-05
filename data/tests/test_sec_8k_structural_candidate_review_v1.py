import json

from herd.sec_8k_structural_candidate_review_v1 import PROTOCOL, evaluate, expected_rows


def test_initial_unseen_review_promotes_nothing() -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    report = evaluate(protocol, expected_rows(protocol))

    assert report["status"] == "PENDING_UNSEEN_SOURCE_REVIEW"
    assert report["identity_promotion_allowed"] is False
    assert report["development_rows_pooled"] == 0


def test_five_valid_rows_are_still_too_small_for_precision_gate() -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    rows = expected_rows(protocol)
    for row in rows:
        row["decision"] = "VALID"
        row["approved_symbol"] = row["candidate_symbols"].split("|")[0]
        row["review_note"] = "source checked"

    report = evaluate(protocol, rows)

    assert report["decision_counts"] == {"VALID": 5}
    assert report["status"] == "UNSEEN_REVIEW_COMPLETE_INSUFFICIENT_FOR_PRECISION_GATE"
    assert report["minimum_independent_reviewed_rows_met"] is False
    assert report["identity_promotion_allowed"] is False
    assert report["next_stage"] == "EXPAND_SEC_8K_STRUCTURAL_EVALUATION_POPULATION"
