import json
from pathlib import Path

from herd.sec_form4_accession_catalog_v1 import _filing_rows, load_protocol


def test_protocol_is_development_only_and_keeps_footnotes():
    protocol = load_protocol()
    assert protocol["scope"]["role"] == "PARSER_AND_SOURCE_REVIEW_DEVELOPMENT_ONLY"
    assert "DROP_FOOTNOTES" in protocol["forbidden"]
    assert protocol["policy"]["direction_hypothesis_allowed"] is False


def test_filing_rows_supports_recent_and_history_shapes():
    columns = {
        "form": ["4", "8-K"],
        "filingDate": ["2020-01-01", "2020-01-02"],
        "accessionNumber": ["0001-20-000001", "0001-20-000002"],
    }
    assert _filing_rows(columns)[0]["form"] == "4"
    assert _filing_rows({"filings": {"recent": columns}})[1]["form"] == "8-K"


def test_filing_rows_rejects_misaligned_columns():
    try:
        _filing_rows({"form": ["4"], "filingDate": []})
    except ValueError as error:
        assert "inconsistent" in str(error)
    else:
        raise AssertionError("misaligned SEC columns must fail closed")
