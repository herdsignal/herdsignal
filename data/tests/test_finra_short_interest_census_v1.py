import json
from datetime import date
from email.message import Message
from pathlib import Path

from herd.finra_short_interest_census_v1 import (
    _sha256_bytes,
    _write_version,
    derive_publication_date,
    discover_urls,
    extract_official_urls,
    parse_file,
)


REQUIRED = [
    "accountingYearMonthNumber",
    "symbolCode",
    "issueName",
    "issuerServicesGroupExchangeCode",
    "marketClassCode",
    "currentShortPositionQuantity",
    "previousShortPositionQuantity",
    "stockSplitFlag",
    "averageDailyVolumeQuantity",
    "daysToCoverQuantity",
    "revisionFlag",
    "changePercent",
    "changePreviousNumber",
    "settlementDate",
]


def _sample(current: str = "100", revision: str = "") -> bytes:
    header = "|".join(REQUIRED)
    row = "|".join([
        "20260630",
        "TEST",
        "Test Inc.",
        "A",
        "NYSE",
        current,
        "90",
        "",
        "1000",
        "1.00",
        revision,
        "11.11",
        "10",
        "2026-06-30",
    ])
    return f"{header}\n{row}\n".encode()


def test_parser_preserves_official_pipe_schema_and_revision_flag():
    parsed = parse_file(_sample(revision="R"), REQUIRED)
    assert parsed.settlement_date == "2026-06-30"
    assert parsed.row_count == 1
    assert parsed.symbols == {"TEST"}
    assert parsed.markets == {"NYSE"}
    assert parsed.revision_rows == 1


def test_publication_date_is_seventh_market_business_day():
    assert derive_publication_date(date(2026, 1, 15)) == date(2026, 1, 27)
    assert derive_publication_date(date(2026, 3, 31)) == date(2026, 4, 10)
    assert derive_publication_date(date(2026, 6, 30)) == date(2026, 7, 10)


def test_discovery_accepts_only_official_dated_urls_inside_locked_window():
    html = """
    https://cdn.finra.org/equity/otcmarket/biweekly/shrt20210528.csv
    https://cdn.finra.org/equity/otcmarket/biweekly/shrt20210615.csv
    https://evil.example/shrt20210630.csv
    https://cdn.finra.org/equity/otcmarket/biweekly/shrt20260731.csv
    """
    urls = extract_official_urls(html, date(2021, 6, 1), date(2026, 7, 23))
    assert urls == [
        "https://cdn.finra.org/equity/otcmarket/biweekly/shrt20210615.csv"
    ]


def test_schedule_discovery_excludes_not_yet_published_settlement_date():
    protocol = {
        "official_source": {},
        "collection_window": {
            "minimum_settlement_date": "2026-06-01",
            "as_of_date": "2026-07-23",
        },
    }
    urls = discover_urls(protocol)
    assert urls[-1].endswith("shrt20260630.csv")
    assert not any("20260715" in url for url in urls)


def test_new_year_saturday_does_not_close_preceding_friday():
    protocol = {
        "official_source": {},
        "collection_window": {
            "minimum_settlement_date": "2021-12-01",
            "as_of_date": "2022-01-20",
        },
    }
    urls = discover_urls(protocol)
    assert any(url.endswith("shrt20211231.csv") for url in urls)
    assert not any(url.endswith("shrt20211230.csv") for url in urls)


def test_append_only_storage_keeps_distinct_hash_versions(tmp_path: Path):
    headers = Message()
    headers["ETag"] = '"fixture"'
    first = _sample("100")
    second = _sample("101")
    first_parsed = parse_file(first, REQUIRED)
    second_parsed = parse_file(second, REQUIRED)
    first_hash = _sha256_bytes(first)
    second_hash = _sha256_bytes(second)

    first_raw, first_receipt, first_created = _write_version(
        tmp_path, first_parsed, first, first_hash, "https://cdn.finra.org/fixture",
        headers, "2026-07-23T00:00:00+00:00"
    )
    _, _, duplicate_created = _write_version(
        tmp_path, first_parsed, first, first_hash, "https://cdn.finra.org/fixture",
        headers, "2026-07-24T00:00:00+00:00"
    )
    second_raw, second_receipt, second_created = _write_version(
        tmp_path, second_parsed, second, second_hash, "https://cdn.finra.org/fixture",
        headers, "2026-07-25T00:00:00+00:00"
    )

    assert first_created is True
    assert duplicate_created is False
    assert second_created is True
    assert first_raw != second_raw
    assert first_raw.read_bytes() == first
    assert second_raw.read_bytes() == second
    assert first_receipt.exists() and second_receipt.exists()
    assert json.loads(first_receipt.read_text())["sha256"] == first_hash
