import csv
import hashlib
import json

from herd.sec_form4_review_workbench_v1 import build_payload, render


XML = b"""<ownershipDocument><nonDerivativeTransaction><transactionCoding><transactionCode>P</transactionCode></transactionCoding></nonDerivativeTransaction></ownershipDocument>"""


def test_workbench_binds_locked_atomic_transaction_to_raw_xml(tmp_path):
    corpus = tmp_path / "corpus"
    (corpus / "raw").mkdir(parents=True)
    digest = hashlib.sha256(XML).hexdigest()
    (corpus / "raw" / f"{digest}.xml").write_bytes(XML)
    with (corpus / "index.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source_sha256", "path", "source_url"])
        writer.writeheader()
        writer.writerow({
            "source_sha256": digest,
            "path": f"raw/{digest}.xml",
            "source_url": "https://www.sec.gov/example",
        })
    (corpus / "manifest.json").write_text("{}")
    protocol = tmp_path / "protocol.json"
    protocol.write_text(json.dumps({
        "status": "LOCKED_BEFORE_HUMAN_SOURCE_REVIEW",
        "required_checks": ["transactionCode"],
    }))
    review = tmp_path / "review.csv"
    row = {
        "atomicTransactionId": "a",
        "transactionIndex": "0",
        "reviewHash": "h",
        "issuerCik": "1",
        "candidateTickers": "TST",
        "accessionNumber": "x",
        "transactionCode": "P",
        "economicClass": "OPEN_MARKET_PURCHASE",
        "economicGroup": "PURCHASE",
        "sourceSha256": digest,
        "rawFootnotes": "{}",
        "reviewDecision": "PENDING",
        "reviewNotes": "",
    }
    with review.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    payload, manifest = build_payload(review, corpus, protocol)
    assert payload[0]["rawTransactionXml"].startswith("<nonDerivativeTransaction>")
    assert manifest["automatic_valid_labels_created"] is False
    output = tmp_path / "review.html"
    render(payload, manifest, output)
    assert "가격 결과·HERD 점수 비공개" in output.read_text()
