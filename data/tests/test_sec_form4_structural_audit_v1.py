import csv
import hashlib
import json

import pandas as pd

from herd.sec_form4_atomic_v1 import parse_document
from herd.sec_form4_structural_audit_v1 import audit


XML = b"""<ownershipDocument><documentType>4</documentType><periodOfReport>2024-01-01</periodOfReport><issuer><issuerCik>1</issuerCik><issuerName>Test</issuerName><issuerTradingSymbol>TST</issuerTradingSymbol></issuer><reportingOwner><reportingOwnerId><rptOwnerCik>2</rptOwnerCik><rptOwnerName>Owner</rptOwnerName></reportingOwnerId></reportingOwner><nonDerivativeTransaction><securityTitle><value>Common</value></securityTitle><transactionDate><value>2024-01-01</value></transactionDate><transactionCoding><transactionCode>P</transactionCode></transactionCoding><transactionAmounts><transactionShares><value>10</value></transactionShares><transactionPricePerShare><value>5</value></transactionPricePerShare><transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode></transactionAmounts><postTransactionAmounts><sharesOwnedFollowingTransaction><value>20</value></sharesOwnedFollowingTransaction></postTransactionAmounts><ownershipNature><directOrIndirectOwnership><value>D</value></directOrIndirectOwnership></ownershipNature></nonDerivativeTransaction></ownershipDocument>"""


def _inputs(tmp_path, corrupt=False):
    corpus = tmp_path / "corpus"
    (corpus / "raw").mkdir(parents=True)
    digest = hashlib.sha256(XML).hexdigest()
    path = corpus / "raw" / f"{digest}.xml"
    path.write_bytes(XML)
    source = {
        "source_sha256": digest,
        "path": f"raw/{digest}.xml",
        "source_url": "https://sec.gov/example",
        "acceptance_datetime": "2024-01-02T01:00:00.000Z",
    }
    with (corpus / "index.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(source))
        writer.writeheader()
        writer.writerow(source)
    metadata = {
        "issuer_cik": "0000000001",
        "candidate_tickers": "TST",
        "accession_number": "x",
        "filing_date": "2024-01-02",
        "acceptance_datetime": source["acceptance_datetime"],
        "source_sha256": digest,
    }
    row = parse_document(XML, metadata)[0]
    row.update({
        "transactionIndex": 0,
        "candidateTickers": "TST",
        "reviewDecision": "PENDING",
    })
    if corrupt:
        row["transactionShares"] = "999"
    review = tmp_path / "review.csv"
    pd.DataFrame([row]).to_csv(review, index=False)
    protocol = tmp_path / "protocol.json"
    protocol.write_text(json.dumps({
        "required_checks": [
            "issuerCik", "reportingOwner", "securityTitle", "transactionDate",
            "transactionCode", "economicClass", "economicGroup",
            "transactionShares",
            "transactionPricePerShare", "acquiredDisposedCode",
            "sharesOwnedFollowingTransaction", "directOrIndirectOwnership",
            "natureOfOwnership", "footnoteIds", "footnoteText", "isDerivative",
            "tenB5OneStatus", "acceptanceDatetime",
        ]
    }))
    return review, corpus, protocol


def test_independent_audit_matches_raw_fields_without_labeling_valid(tmp_path):
    review, corpus, protocol = _inputs(tmp_path)
    result = audit(
        review, corpus, protocol, tmp_path / "detail.csv", tmp_path / "report.json"
    )
    assert result["status"] == "STRUCTURAL_AUDIT_PASSED"
    assert result["human_valid_labels_created"] is False


def test_independent_audit_detects_corrupted_parser_field(tmp_path):
    review, corpus, protocol = _inputs(tmp_path, corrupt=True)
    result = audit(
        review, corpus, protocol, tmp_path / "detail.csv", tmp_path / "report.json"
    )
    assert result["status"] == "STRUCTURAL_AUDIT_FAILED"
    assert result["mismatch_field_counts"] == {"transactionShares": 1}
