import csv
import json
from pathlib import Path

from herd.sec_form4_source_corpus_v1 import Form4CorpusError, collect


XML = b"""<?xml version="1.0"?><ownershipDocument><issuer><issuerCik>1</issuerCik></issuer></ownershipDocument>"""


class Response:
    content = XML

    def raise_for_status(self):
        return None


class Session:
    def __init__(self):
        self.headers = {}
        self.urls = []

    def get(self, url, timeout):
        self.urls.append(url)
        return Response()


def _sample(path: Path):
    row = {
        "issuer_cik": "0000000001",
        "candidate_tickers": "TEST",
        "reporting_owner_cik": "0000000002",
        "accession_number": "0000000002-24-000001",
        "form": "4",
        "filing_date": "2024-01-02",
        "report_date": "2024-01-01",
        "acceptance_datetime": "2024-01-02T12:00:00.000Z",
        "primary_document": "form4.xml",
        "source_url": "https://www.sec.gov/Archives/form4.xml",
    }
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)


def test_collect_preserves_metadata_and_hashes_raw_xml(tmp_path):
    sample = tmp_path / "sample.csv"
    _sample(sample)
    result = collect(
        sample, tmp_path, snapshot_id="form4-test", user_agent="test a@b.com",
        session=Session(),
    )
    manifest = json.loads((result / "manifest.json").read_text())
    assert manifest["documents"] == 1
    assert manifest["price_outcomes_opened"] is False
    index = list(csv.DictReader((result / "index.csv").open()))
    assert index[0]["issuer_cik"] == "0000000001"
    assert (result / index[0]["path"]).read_bytes() == XML


def test_collect_refuses_overwrite(tmp_path):
    sample = tmp_path / "sample.csv"
    _sample(sample)
    (tmp_path / "form4-test").mkdir()
    try:
        collect(
            sample, tmp_path, snapshot_id="form4-test",
            user_agent="test a@b.com", session=Session(),
        )
    except Form4CorpusError as error:
        assert "exists" in str(error)
    else:
        raise AssertionError("immutable corpus must not be overwritten")
