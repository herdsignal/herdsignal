from __future__ import annotations

from datetime import date

from herd.append_only_ledger import read_ledger
from herd.sec_earnings_event_ledger_v1 import collect_events, extract_events


def _payload() -> dict:
    return {
        "filings": {
            "recent": {
                "accessionNumber": ["0001-26-000001", "0001-26-000002", "0001-26-000003"],
                "acceptanceDateTime": [
                    "2026-08-04T20:05:01.000Z",
                    "2026-08-05T12:00:00.000Z",
                    "2026-08-06T12:00:00.000Z",
                ],
                "filingDate": ["2026-08-04", "2026-08-05", "2026-08-06"],
                "reportDate": ["2026-06-30", "2026-06-30", "2026-06-30"],
                "form": ["8-K", "10-Q", "8-K"],
                "items": ["2.02,9.01", "", "7.01"],
                "primaryDocument": ["earnings.htm", "form10q.htm", "other.htm"],
            }
        }
    }


def test_extracts_only_time_valid_quarterly_earnings_disclosures() -> None:
    rows = extract_events(
        "ACME",
        "0000000001",
        [("https://data.sec.gov/submissions/CIK0000000001.json", _payload())],
        accepted_on_or_after=date(2026, 8, 3),
    )
    assert [row["event_kind"] for row in rows] == [
        "EARNINGS_RESULT_8K_ITEM_2_02",
        "QUARTERLY_REPORT_10Q",
    ]
    assert rows[0]["information_time"] == "EDGAR_ACCEPTANCE_DATETIME"


def test_collection_appends_once_and_never_stores_contact(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    loader = lambda cik: [("fixture://submissions", _payload())]
    first = collect_events(
        {"ACME": "0000000001"},
        path,
        user_agent="HerdSignal test owner@example.com",
        accepted_on_or_after=date(2026, 8, 3),
        delay_seconds=0.11,
        payload_loader=loader,
    )
    second = collect_events(
        {"ACME": "0000000001"},
        path,
        user_agent="HerdSignal test owner@example.com",
        accepted_on_or_after=date(2026, 8, 3),
        delay_seconds=0.11,
        payload_loader=loader,
    )
    assert first["appended"] == 2
    assert second["duplicates"] == 2
    assert "owner@example.com" not in path.read_text()
    assert len(read_ledger(path)) == 2
