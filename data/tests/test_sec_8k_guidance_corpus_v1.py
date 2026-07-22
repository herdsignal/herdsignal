import json
import gzip
import hashlib
from pathlib import Path

import pandas as pd

from herd.sec_8k_guidance_corpus_v1 import _text_document, collect_documents, filing_rows


ROOT = Path(__file__).resolve().parents[1]


def test_submission_rows_preserve_acceptance_and_items():
    recent = {
        "accessionNumber": ["0000000001-24-000001"], "filingDate": ["2024-01-02"],
        "acceptanceDateTime": ["2024-01-02T21:00:00.000Z"], "form": ["8-K"],
        "primaryDocument": ["report.htm"], "items": ["2.02,9.01"],
    }
    assert filing_rows({"filings": {"recent": recent}})[0]["acceptanceDateTime"].endswith("Z")
    assert filing_rows(recent)[0]["items"] == "2.02,9.01"


def test_document_filter_excludes_xbrl_but_keeps_text_attachments():
    protocol = json.loads((ROOT / "herd/sec_8k_guidance_corpus_v1.json").read_text())
    config = protocol["download"]
    assert _text_document("exhibit991.htm", {"size": 1000}, config)
    assert not _text_document("company_cal.xml", {"size": 1000}, config)
    assert not _text_document("0001193125-12-002955-index-headers.html", {"size": 0}, config)
    assert not _text_document("0001193125-12-002955.txt", {"size": 0}, config)
    assert not _text_document("large.txt", {"size": 10000001}, config)


def test_protocol_forbids_consensus_inference_and_early_direction_labels():
    protocol = json.loads((ROOT / "herd/sec_8k_guidance_corpus_v1.json").read_text())
    assert "INFER_ANALYST_CONSENSUS" in protocol["forbidden"]
    assert "CLASSIFY_UP_DOWN_FLAT_BEFORE_COVERAGE_AUDIT" in protocol["forbidden"]


def test_collection_resumes_from_matching_checkpoint_without_refetching(monkeypatch, tmp_path):
    accessions = ["0000000001-24-000001", "0000000002-24-000002"]
    catalog = pd.DataFrame([
        {
            "ticker": ticker, "cik": cik, "accession_number": accession,
            "accepted_at": f"2024-01-0{position}T21:00:00.000Z", "items": "2.02",
            "primary_document": "report.htm", "archive_dir": f"https://example.test/{position}",
            "index_json_url": f"https://example.test/{position}/index.json",
        }
        for position, (ticker, cik, accession) in enumerate(
            [("AAA", "0000000001", accessions[0]), ("BBB", "0000000002", accessions[1])], start=1
        )
    ])
    output_root = tmp_path / "sec"
    work = output_root / ".snapshot.tmp-resume"
    raw = work / "raw"
    raw.mkdir(parents=True)
    first_content = b"first filing"
    first_digest = hashlib.sha256(first_content).hexdigest()
    with gzip.open(raw / f"{first_digest}.gz", "wb") as stream:
        stream.write(first_content)
    first_row = {
        "ticker": "AAA", "cik": "0000000001", "accession_number": accessions[0],
        "accepted_at": "2024-01-01T21:00:00.000Z", "items": "2.02",
        "document_name": "report.htm", "document_role": "PRIMARY",
        "source_url": "https://example.test/1/report.htm", "source_sha256": first_digest,
        "source_bytes": len(first_content), "path": f"raw/{first_digest}.gz",
        "classification_status": "NOT_CLASSIFIED",
    }
    pd.DataFrame([first_row]).to_csv(work / "checkpoint-index.csv", index=False)
    (work / "checkpoint-failures.json").write_text("[]\n")
    fingerprint = hashlib.sha256("\n".join(sorted(accessions)).encode()).hexdigest()
    (work / "checkpoint.json").write_text(json.dumps({
        "catalog_sha256": fingerprint, "completed_accessions": [accessions[0]],
    }))

    requested = []

    class Response:
        status_code = 200

        def __init__(self, url):
            self.url = url
            self.content = b"second filing"

        def json(self):
            return {"directory": {"item": []}}

    def fake_get(_session, url, timeout):
        requested.append(url)
        return Response(url)

    monkeypatch.setattr("requests.Session.get", fake_get)
    protocol = {
        "download": {
            "minimum_request_interval_seconds": 0,
            "maximum_workers": 1,
            "checkpoint_every_filings": 1,
            "archive_base": "https://example.test",
            "extensions": [".htm"],
            "exclude_filename_patterns": [],
            "maximum_text_document_bytes": 10000,
        }
    }
    final = collect_documents(catalog, protocol, output_root, "snapshot", "test@example.com")
    index = pd.read_csv(final / "index.csv", dtype={"cik": str})
    assert set(index["accession_number"]) == set(accessions)
    assert all("/1/" not in url for url in requested)
    assert json.loads((final / "manifest.json").read_text())["filings_collected"] == 2
