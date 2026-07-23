import pandas as pd

from herd.sec_form4_census_gate_v2 import crosscheck_primary_xml


def test_primary_xml_crosscheck_normalizes_decimal_representation():
    transactions = pd.DataFrame([{
        "accessionNumber": "0001",
        "transactionDate": "2026-01-02",
        "transactionCode": "P",
        "transactionShares": "100.0",
        "transactionPricePerShare": "10",
        "acquiredDisposedCode": "A",
        "sharesOwnedFollowingTransaction": "1000.000",
        "directOrIndirectOwnership": "D",
        "isDerivative": False,
    }])
    adjudicated = pd.DataFrame([{
        "atomicTransactionId": "review-1",
        "accessionNumber": "0001",
        "reviewDecision": "VALID",
        "transactionDate": "2026-01-02",
        "transactionCode": "P",
        "transactionShares": "100.0000",
        "transactionPricePerShare": "10.0",
        "acquiredDisposedCode": "A",
        "sharesOwnedFollowingTransaction": "1000",
        "directOrIndirectOwnership": "D",
        "isDerivative": "False",
    }])
    detail, report = crosscheck_primary_xml(transactions, adjudicated)
    assert bool(detail.iloc[0]["exactMatch"])
    assert report["exact_match_rate"] == 1.0


def test_primary_xml_crosscheck_uses_sec_two_decimal_precision_and_date():
    transactions = pd.DataFrame([{
        "accessionNumber": "0001",
        "transactionDate": "2026-01-02",
        "transactionCode": "P",
        "transactionShares": "13.58",
        "transactionPricePerShare": "47.82",
        "acquiredDisposedCode": "A",
        "sharesOwnedFollowingTransaction": "1000.0",
        "directOrIndirectOwnership": "D",
        "isDerivative": False,
    }])
    adjudicated = pd.DataFrame([{
        "atomicTransactionId": "review-1",
        "accessionNumber": "0001",
        "reviewDecision": "VALID",
        "filingDate": "2026-01-03",
        "transactionDate": "2026-01-02-05:00",
        "transactionCode": "P",
        "transactionShares": "13.5806",
        "transactionPricePerShare": "47.8150",
        "acquiredDisposedCode": "A",
        "sharesOwnedFollowingTransaction": "1000.004",
        "directOrIndirectOwnership": "D",
        "isDerivative": "False",
    }])
    detail, report = crosscheck_primary_xml(transactions, adjudicated)
    assert bool(detail.iloc[0]["exactMatch"])
    assert report["exact_match_rate"] == 1.0


def test_primary_xml_crosscheck_marks_wrong_direction_invalid():
    transactions = pd.DataFrame([{
        "accessionNumber": "0001",
        "transactionDate": "2026-01-02",
        "transactionCode": "S",
        "transactionShares": "100",
        "transactionPricePerShare": "10",
        "acquiredDisposedCode": "D",
        "sharesOwnedFollowingTransaction": "900",
        "directOrIndirectOwnership": "D",
        "isDerivative": False,
    }])
    adjudicated = pd.DataFrame([{
        "atomicTransactionId": "review-1",
        "accessionNumber": "0001",
        "reviewDecision": "VALID",
        "transactionDate": "2026-01-02",
        "transactionCode": "P",
        "transactionShares": "100",
        "transactionPricePerShare": "10",
        "acquiredDisposedCode": "A",
        "sharesOwnedFollowingTransaction": "1000",
        "directOrIndirectOwnership": "D",
        "isDerivative": "False",
    }])
    detail, report = crosscheck_primary_xml(transactions, adjudicated)
    assert not bool(detail.iloc[0]["exactMatch"])
    assert report["exact_match_rate"] == 0.0
