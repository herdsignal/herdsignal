import pandas as pd

from herd.sec_form4_review_ledger_v1 import ReviewLedgerError, merge


def _rows():
    return [
        {
            "atomicTransactionId": "a",
            "reviewHash": "h1",
            "issuerCik": "1",
            "accessionNumber": "x",
            "transactionCode": "P",
            "economicClass": "OPEN_MARKET_PURCHASE",
            "sourceSha256": "s1",
            "reviewDecision": "PENDING",
            "reviewNotes": "",
        },
        {
            "atomicTransactionId": "b",
            "reviewHash": "h2",
            "issuerCik": "2",
            "accessionNumber": "y",
            "transactionCode": "S",
            "economicClass": "OPEN_MARKET_SALE",
            "sourceSha256": "s2",
            "reviewDecision": "PENDING",
            "reviewNotes": "",
        },
    ]


def test_merge_preserves_locked_identity_and_updates_only_decisions(tmp_path):
    queue = tmp_path / "queue.csv"
    decisions = tmp_path / "decisions.csv"
    rows = _rows()
    pd.DataFrame(rows).to_csv(queue, index=False)
    rows[0]["reviewDecision"] = "VALID"
    rows[1]["reviewDecision"] = "AMBIGUOUS"
    rows[1]["reviewNotes"] = "source footnote is not unique"
    pd.DataFrame(rows[::-1]).to_csv(decisions, index=False)
    result = merge(
        queue, decisions, tmp_path / "merged.csv", tmp_path / "report.json"
    )
    assert result["decision_counts"] == {"VALID": 1, "AMBIGUOUS": 1}
    merged = pd.read_csv(tmp_path / "merged.csv", dtype=str)
    assert list(merged["atomicTransactionId"]) == ["a", "b"]


def test_merge_rejects_changed_source_identity(tmp_path):
    queue = tmp_path / "queue.csv"
    decisions = tmp_path / "decisions.csv"
    rows = _rows()
    pd.DataFrame(rows).to_csv(queue, index=False)
    rows[0]["sourceSha256"] = "changed"
    pd.DataFrame(rows).to_csv(decisions, index=False)
    try:
        merge(queue, decisions, tmp_path / "merged.csv", tmp_path / "report.json")
    except ReviewLedgerError as error:
        assert "sourceSha256" in str(error)
    else:
        raise AssertionError("changed source identity must fail closed")
