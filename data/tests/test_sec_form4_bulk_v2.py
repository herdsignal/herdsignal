import csv
import io
import json
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from herd.sec_form4_bulk_v2 import (
    PROTOCOL,
    Form4BulkError,
    download,
    normalize,
    quarters,
    sha256,
    verify_download,
    verify_normalized,
)


def _protocol(path: Path, start: str = "2026Q2", end: str = "2026Q2") -> Path:
    payload = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    payload["source"]["start_quarter"] = start
    payload["source"]["end_quarter"] = end
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _tsv(rows: list[dict]) -> bytes:
    stream = io.StringIO()
    writer = csv.DictWriter(
        stream,
        fieldnames=list(rows[0]),
        delimiter="\t",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def _zip_payload() -> bytes:
    tables = {
        "SUBMISSION.tsv": [{
            "ACCESSION_NUMBER": "0000000001-26-000001",
            "FILING_DATE": "15-APR-2026",
            "PERIOD_OF_REPORT": "14-APR-2026",
            "DOCUMENT_TYPE": "4",
            "ISSUERCIK": "0000000001",
            "ISSUERNAME": "Independent Inc",
            "ISSUERTRADINGSYMBOL": "IND",
            "REMARKS": "",
            "AFF10B5ONE": "0",
        }],
        "REPORTINGOWNER.tsv": [{
            "ACCESSION_NUMBER": "0000000001-26-000001",
            "RPTOWNERCIK": "0000000099",
            "RPTOWNERNAME": "Owner",
            "RPTOWNER_RELATIONSHIP": "Officer",
            "RPTOWNER_TITLE": "CEO",
        }],
        "NONDERIV_TRANS.tsv": [{
            "ACCESSION_NUMBER": "0000000001-26-000001",
            "NONDERIV_TRANS_SK": "10",
            "SECURITY_TITLE": "Common Stock",
            "TRANS_DATE": "14-APR-2026",
            "TRANS_CODE": "P",
            "EQUITY_SWAP_INVOLVED": "0",
            "TRANS_SHARES": "100.0",
            "TRANS_PRICEPERSHARE": "10.0",
            "TRANS_ACQUIRED_DISP_CD": "A",
            "SHRS_OWND_FOLWNG_TRANS": "1000.0",
            "DIRECT_INDIRECT_OWNERSHIP": "D",
            "NATURE_OF_OWNERSHIP": "",
            "TRANS_PRICEPERSHARE_FN": "F1",
        }],
        "DERIV_TRANS.tsv": [{
            "ACCESSION_NUMBER": "0000000001-26-000001",
            "DERIV_TRANS_SK": "20",
            "SECURITY_TITLE": "Option",
            "TRANS_DATE": "14-APR-2026",
            "TRANS_CODE": "M",
            "EQUITY_SWAP_INVOLVED": "0",
            "TRANS_SHARES": "10.0",
            "TRANS_PRICEPERSHARE": "1.0",
            "TRANS_ACQUIRED_DISP_CD": "A",
            "SHRS_OWND_FOLWNG_TRANS": "10.0",
            "DIRECT_INDIRECT_OWNERSHIP": "D",
            "NATURE_OF_OWNERSHIP": "",
        }],
        "FOOTNOTES.tsv": [{
            "ACCESSION_NUMBER": "0000000001-26-000001",
            "FOOTNOTE_ID": "F1",
            "FOOTNOTE_TXT": "Open market purchase.",
        }],
    }
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, content in tables.items():
            archive.writestr(name, _tsv(content))
    return stream.getvalue()


class _Response:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        return None


class _Session:
    def __init__(self, content: bytes):
        self.content = content
        self.headers = {}
        self.calls = 0

    def get(self, _url, timeout):
        assert timeout == 120
        self.calls += 1
        return _Response(self.content)


def test_quarters_are_contiguous():
    assert quarters("2025Q4", "2026Q2") == ["2025Q4", "2026Q1", "2026Q2"]
    with pytest.raises(Form4BulkError):
        quarters("2026Q3", "2026Q2")


def test_download_is_resumable_and_hash_verified(tmp_path):
    protocol = _protocol(tmp_path / "protocol.json")
    session = _Session(_zip_payload())
    snapshot = download(
        tmp_path,
        "fixture-census",
        protocol_path=protocol,
        user_agent="fixture research fixture@example.com",
        session=session,
    )
    assert session.calls == 1
    assert verify_download(snapshot, protocol_path=protocol)["quarter_count"] == 1
    assert download(
        tmp_path,
        "fixture-census",
        protocol_path=protocol,
        user_agent="fixture research fixture@example.com",
        session=session,
    ) == snapshot
    assert session.calls == 1


def test_normalize_preserves_owner_footnote_and_authority_boundary(tmp_path):
    protocol = _protocol(tmp_path / "protocol.json")
    snapshot = download(
        tmp_path,
        "fixture-census",
        protocol_path=protocol,
        user_agent="fixture research fixture@example.com",
        session=_Session(_zip_payload()),
    )
    independent = tmp_path / "independent.csv"
    pd.DataFrame([{
        "ticker": "IND",
        "cik": "1",
        "eligible": True,
        "rejection_reasons": "",
    }]).to_csv(independent, index=False)
    discovery = tmp_path / "discovery.csv"
    pd.DataFrame([{
        "issuer_cik": "2",
        "candidate_tickers": "OLD",
    }]).to_csv(discovery, index=False)
    result = normalize(
        snapshot,
        independent_universe=independent,
        discovery_catalog=discovery,
        protocol_path=protocol,
    )
    assert result["independent_issuers"] == 1
    assert result["transactions"] == 2
    assert result["operational_action_authority"] is False
    transactions = pd.read_csv(
        snapshot / "normalized/transactions.csv",
        dtype=str,
        keep_default_na=False,
    )
    purchase = transactions[transactions["transactionCode"].eq("P")].iloc[0]
    assert purchase["economicClass"] == "OPEN_MARKET_OR_PRIVATE_PURCHASE"
    assert purchase["reportingOwnerCiks"] == "0000000099"
    assert "Open market purchase" in purchase["referencedFootnoteText"]
    assert verify_normalized(
        snapshot,
        protocol_path=protocol,
    )["price_outcomes_opened"] is False


def test_normalize_excludes_discovery_issuer_overlap(tmp_path):
    protocol = _protocol(tmp_path / "protocol.json")
    snapshot = download(
        tmp_path,
        "fixture-census",
        protocol_path=protocol,
        user_agent="fixture research fixture@example.com",
        session=_Session(_zip_payload()),
    )
    independent = tmp_path / "independent.csv"
    pd.DataFrame([{
        "ticker": "IND",
        "cik": "1",
        "eligible": True,
        "rejection_reasons": "",
    }]).to_csv(independent, index=False)
    discovery = tmp_path / "discovery.csv"
    pd.DataFrame([{
        "issuer_cik": "1",
        "candidate_tickers": "IND",
    }]).to_csv(discovery, index=False)
    result = normalize(
        snapshot,
        independent_universe=independent,
        discovery_catalog=discovery,
        protocol_path=protocol,
    )
    assert result["independent_issuers"] == 0
    assert result["independent_issuer_overlap_excluded"] == 1
    assert result["independent_issuer_overlap_tickers"] == ["IND"]
