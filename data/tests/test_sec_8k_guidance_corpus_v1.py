import json
from pathlib import Path

from herd.sec_8k_guidance_corpus_v1 import _text_document, filing_rows


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
