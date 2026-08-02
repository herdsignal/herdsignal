from pathlib import Path

from herd.append_only_ledger import append_unique
from herd.ticker_disjoint_sec_earnings_census_v1 import materialize_catalog


def test_catalog_materialization_is_deterministic_and_scoped(tmp_path: Path):
    ledger = tmp_path / "events.jsonl"
    catalog = tmp_path / "catalog.csv"
    base = {
        "cik": "0000000001", "accession_number": "a", "filing_date": "2020-01-01",
        "report_date": "2019-12-31", "form": "10-Q", "items": "",
        "event_kind": "QUARTERLY_REPORT_10Q", "primary_document": "a.htm",
        "source_url": "https://example.test", "source_authority": "SEC_EDGAR_SUBMISSIONS_API",
        "information_time": "EDGAR_ACCEPTANCE_DATETIME",
    }
    append_unique(ledger, [
        {**base, "event_id": "b", "ticker": "OUT", "accepted_at": "2020-02-01T00:00:00Z"},
        {**base, "event_id": "a", "ticker": "IN", "accepted_at": "2020-01-01T00:00:00Z"},
    ], identity_field="event_id")

    frame = materialize_catalog(ledger, {"IN": "0000000001"}, catalog)

    assert frame["event_id"].tolist() == ["a"]
    assert catalog.is_file()
