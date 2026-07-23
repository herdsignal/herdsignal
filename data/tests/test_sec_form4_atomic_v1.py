import json

from herd.sec_form4_atomic_v1 import IssuerCikMismatch, parse_document


XML = b"""<?xml version="1.0"?>
<ownershipDocument>
  <documentType>4</documentType><periodOfReport>2024-01-01</periodOfReport>
  <issuer><issuerCik>1</issuerCik><issuerName>Test</issuerName><issuerTradingSymbol>TST</issuerTradingSymbol></issuer>
  <reportingOwner><reportingOwnerId><rptOwnerCik>2</rptOwnerCik><rptOwnerName>Owner</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship><isDirector>1</isDirector><isOfficer>1</isOfficer><officerTitle>CEO</officerTitle></reportingOwnerRelationship></reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <securityTitle><value>Common</value></securityTitle>
      <transactionDate><value>2024-01-01</value></transactionDate>
      <transactionCoding><transactionCode>P</transactionCode><equitySwapInvolved>0</equitySwapInvolved></transactionCoding>
      <transactionAmounts><transactionShares><value>10</value></transactionShares><transactionPricePerShare><value>5.5</value><footnoteId id="F1"/></transactionPricePerShare><transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode></transactionAmounts>
      <postTransactionAmounts><sharesOwnedFollowingTransaction><value>100</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
      <ownershipNature><directOrIndirectOwnership><value>D</value></directOrIndirectOwnership></ownershipNature>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <transactionCoding><transactionCode>F</transactionCode></transactionCoding>
      <transactionAmounts><transactionShares><value>2</value></transactionShares></transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
  <footnotes><footnote id="F1">Transaction under a Rule 10b5-1 plan.</footnote></footnotes>
</ownershipDocument>"""


def metadata():
    return {
        "issuer_cik": "0000000001", "candidate_tickers": "TST",
        "accession_number": "0000000002-24-000001",
        "filing_date": "2024-01-02",
        "acceptance_datetime": "2024-01-02T12:00:00.000Z",
        "source_sha256": "abc",
    }


def test_parser_keeps_atomic_values_owners_and_footnotes():
    rows = parse_document(XML, metadata())
    assert len(rows) == 2
    assert rows[0]["economicClass"] == "OPEN_MARKET_PURCHASE"
    assert rows[0]["transactionPricePerShare"] == "5.5"
    assert rows[0]["directOrIndirectOwnership"] == "D"
    assert rows[0]["tenB5OneStatus"] == "TRUE"
    assert "10b5-1" in rows[0]["footnoteText"]
    assert json.loads(rows[0]["reportingOwner"])[0]["officerTitle"] == "CEO"
    assert rows[1]["economicClass"] == "TAX_OR_EXERCISE_WITHHOLDING"


def test_parser_rejects_issuer_cik_mismatch():
    wrong = metadata()
    wrong["issuer_cik"] = "0000000009"
    try:
        parse_document(XML, wrong)
    except IssuerCikMismatch as error:
        assert "mismatch" in str(error)
    else:
        raise AssertionError("issuer mismatch must fail closed")
