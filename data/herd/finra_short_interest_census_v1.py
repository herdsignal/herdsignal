"""FINRA biweekly short-interest files를 append-only SHA-256 corpus로 고정한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from email.message import Message
from email.parser import BytesHeaderParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_name("finra_short_interest_immutable_census_v1.json")
TRACKED_MANIFEST = Path(__file__).with_name(
    "finra_short_interest_immutable_census_v1_manifest.json"
)
FILE_URL_RE = re.compile(
    r"https://cdn\.finra\.org/equity/otcmarket/biweekly/"
    r"shrt(?P<date>[0-9]{8})\.csv"
)


@dataclass(frozen=True)
class ParsedFile:
    settlement_date: str
    row_count: int
    symbols: frozenset[str]
    markets: frozenset[str]
    revision_rows: int
    columns: tuple[str, ...]


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _root_path(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f"path escapes repository: {relative}")
    return path


def load_and_verify_protocol(path: Path = PROTOCOL) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol["status"] != "LOCKED_BEFORE_COLLECTION":
        raise ValueError("FINRA census protocol is not locked before collection")
    artifacts = [
        protocol["prerequisite"],
        *protocol["identifier_policy"]["locked_inputs"],
    ]
    for artifact in artifacts:
        actual = _sha256_file(_root_path(artifact["path"]))
        if actual != artifact["sha256"]:
            raise ValueError(f"locked input changed: {artifact['path']}")
    prerequisite = json.loads(
        _root_path(protocol["prerequisite"]["path"]).read_text(encoding="utf-8")
    )
    if prerequisite["status"] != protocol["prerequisite"]["required_status"]:
        raise ValueError("public leading-data prerequisite status changed")
    if prerequisite["next_priority"] != protocol["prerequisite"]["required_next_priority"]:
        raise ValueError("public leading-data prerequisite next priority changed")
    return protocol


def _nth_weekday(year: int, month: int, weekday: int, ordinal: int) -> date:
    current = date(year, month, 1)
    shift = (weekday - current.weekday()) % 7
    return current + timedelta(days=shift + 7 * (ordinal - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        current = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        current = date(year, month + 1, 1) - timedelta(days=1)
    return current - timedelta(days=(current.weekday() - weekday) % 7)


def _observed(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _new_year_market_holiday(year: int) -> date | None:
    day = date(year, 1, 1)
    if day.weekday() == 5:
        # NYSE Rule 7.2 does not close the preceding Friday when Jan 1 is Saturday.
        return None
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _easter_sunday(year: int) -> date:
    # Anonymous Gregorian algorithm.
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def us_securities_market_holidays(year: int) -> frozenset[date]:
    holidays = {
        _nth_weekday(year, 1, 0, 3),  # Martin Luther King Jr. Day
        _nth_weekday(year, 2, 0, 3),  # Washington's Birthday
        _easter_sunday(year) - timedelta(days=2),  # Good Friday
        _last_weekday(year, 5, 0),  # Memorial Day
        _observed(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),  # Labor Day
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving
        _observed(date(year, 12, 25)),
    }
    new_year = _new_year_market_holiday(year)
    if new_year is not None:
        holidays.add(new_year)
    if year >= 2022:
        holidays.add(_observed(date(year, 6, 19)))
    return frozenset(holidays)


def derive_publication_date(settlement_date: date) -> date:
    """FINRA 공식 규칙인 결제기준일 후 7번째 영업일을 계산한다."""
    current = settlement_date
    business_days = 0
    while business_days < 7:
        current += timedelta(days=1)
        holidays = us_securities_market_holidays(current.year)
        if current.weekday() < 5 and current not in holidays:
            business_days += 1
    return current


def safe_availability_utc(publication_date: date) -> str:
    # 정확한 당일 게시 시각이 없으므로 다음 날 00:00 ET를 UTC로 환산하지 않고
    # 명시적 local-time 경계로 보존한다. 이후 PIT join은 이 문자열의 날짜+1만 사용한다.
    return f"{publication_date + timedelta(days=1)}T00:00:00[America/New_York]"


def parse_file(content: bytes, required_columns: list[str]) -> ParsedFile:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text), delimiter="|")
    if reader.fieldnames != required_columns:
        raise ValueError(f"unexpected FINRA columns: {reader.fieldnames}")
    rows = list(reader)
    if not rows:
        raise ValueError("empty FINRA short-interest file")
    settlement_dates = {row["settlementDate"] for row in rows}
    accounting_dates = {row["accountingYearMonthNumber"] for row in rows}
    if len(settlement_dates) != 1 or len(accounting_dates) != 1:
        raise ValueError("FINRA file mixes settlement dates")
    settlement_date = next(iter(settlement_dates))
    if settlement_date.replace("-", "") != next(iter(accounting_dates)):
        raise ValueError("accounting date does not match settlement date")
    return ParsedFile(
        settlement_date=settlement_date,
        row_count=len(rows),
        symbols=frozenset(row["symbolCode"].strip() for row in rows),
        markets=frozenset(row["marketClassCode"].strip() for row in rows),
        revision_rows=sum(bool(row["revisionFlag"].strip()) for row in rows),
        columns=tuple(reader.fieldnames),
    )


def extract_official_urls(
    html: str, minimum_date: date, as_of_date: date
) -> list[str]:
    urls: set[str] = set()
    for match in FILE_URL_RE.finditer(html):
        settlement = datetime.strptime(match.group("date"), "%Y%m%d").date()
        if minimum_date <= settlement <= as_of_date:
            urls.add(match.group(0))
    return sorted(urls)


def discover_urls(protocol: dict, timeout: int = 60) -> list[str]:
    source = protocol["official_source"]
    window = protocol["collection_window"]
    minimum = date.fromisoformat(window["minimum_settlement_date"])
    as_of = date.fromisoformat(window["as_of_date"])
    urls: list[str] = []
    current = date(minimum.year, minimum.month, 1)
    while current <= as_of:
        year, month = current.year, current.month
        mid = date(year, month, 15)
        holidays = us_securities_market_holidays(year)
        while mid.weekday() >= 5 or mid in holidays:
            mid -= timedelta(days=1)
        end = (
            date(year + 1, 1, 1) - timedelta(days=1)
            if month == 12
            else date(year, month + 1, 1) - timedelta(days=1)
        )
        while end.weekday() >= 5 or end in holidays:
            end -= timedelta(days=1)
        for settlement in (mid, end):
            # A file is not public merely because its settlement date has passed.
            if (
                minimum <= settlement <= as_of
                and derive_publication_date(settlement) <= as_of
            ):
                stamp = settlement.strftime("%Y%m%d")
                urls.append(
                    "https://cdn.finra.org/equity/otcmarket/biweekly/"
                    f"shrt{stamp}.csv"
                )
        current = (
            date(year + 1, 1, 1)
            if month == 12
            else date(year, month + 1, 1)
        )
    return sorted(set(urls))


def _download(url: str, timeout: int) -> tuple[bytes, Message]:
    command = [
        "curl",
        "-L",
        "--fail",
        "--retry",
        "3",
        "--retry-all-errors",
        "--retry-delay",
        "3",
        "--connect-timeout",
        "30",
        "--max-time",
        str(max(timeout, 180)),
        "--silent",
        "--show-error",
        "--dump-header",
        "-",
        url,
    ]
    result = None
    for attempt in range(4):
        result = subprocess.run(command, check=False, capture_output=True)
        if result.returncode == 0:
            break
        if attempt == 3:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"FINRA download failed after retries: {url}: {detail}")
        time.sleep(5 * (2 ** attempt))
    assert result is not None
    delimiter = b"\r\n\r\n"
    if delimiter not in result.stdout:
        delimiter = b"\n\n"
    header_chain, content = result.stdout.rsplit(delimiter, 1)
    final_header = header_chain.rsplit(delimiter, 1)[-1]
    _, _, header_lines = final_header.partition(b"\n")
    headers = BytesHeaderParser().parsebytes(header_lines)
    return content, headers


def _header(headers: Message, name: str) -> str | None:
    return headers.get(name)


def _write_version(
    corpus_root: Path,
    parsed: ParsedFile,
    content: bytes,
    digest: str,
    url: str,
    headers: Message,
    retrieved_at: str,
) -> tuple[Path, Path, bool]:
    settlement = parsed.settlement_date
    raw_path = corpus_root / "raw" / settlement / f"{digest}.csv"
    receipt_path = corpus_root / "receipts" / settlement / f"{digest}.json"
    existed = raw_path.exists()
    if existed:
        if _sha256_file(raw_path) != digest:
            raise ValueError(f"immutable raw file corrupted: {raw_path}")
    else:
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(content)
    if not receipt_path.exists():
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        publication = derive_publication_date(date.fromisoformat(settlement))
        receipt = {
            "receipt_version": "FINRA_SHORT_INTEREST_FILE_RECEIPT_V1",
            "settlement_date": settlement,
            "derived_publication_date": publication.isoformat(),
            "publication_date_source": (
                "DERIVED_FROM_FINRA_SEVENTH_BUSINESS_DAY_RULE"
            ),
            "safe_availability_time": safe_availability_utc(publication),
            "source_url": url,
            "retrieved_at_utc": retrieved_at,
            "sha256": digest,
            "bytes": len(content),
            "http": {
                "etag": _header(headers, "ETag"),
                "last_modified": _header(headers, "Last-Modified"),
                "content_length": _header(headers, "Content-Length"),
                "content_type": _header(headers, "Content-Type"),
            },
            "schema": list(parsed.columns),
            "row_count": parsed.row_count,
            "symbol_count": len(parsed.symbols),
            "markets": sorted(parsed.markets),
            "revision_flag_rows": parsed.revision_rows,
        }
        receipt_path.write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return raw_path, receipt_path, not existed


def collect(
    protocol_path: Path = PROTOCOL,
    tracked_manifest_path: Path = TRACKED_MANIFEST,
    timeout: int = 60,
) -> dict:
    protocol = load_and_verify_protocol(protocol_path)
    corpus_root = _root_path(protocol["immutable_storage"]["local_root"])
    corpus_root.mkdir(parents=True, exist_ok=True)
    urls = discover_urls(protocol, timeout=timeout)
    if not urls:
        raise ValueError("no official FINRA files discovered")
    entries = []
    new_versions = 0
    retrieved_at = datetime.now(timezone.utc).isoformat()
    resume_incomplete_first_run = not tracked_manifest_path.exists()
    for index, url in enumerate(urls, start=1):
        embedded = FILE_URL_RE.fullmatch(url)
        if not embedded:
            raise ValueError(f"non-official URL escaped discovery: {url}")
        filename_date = datetime.strptime(embedded.group("date"), "%Y%m%d").date()
        settlement = filename_date.isoformat()
        if resume_incomplete_first_run:
            receipts = sorted((corpus_root / "receipts" / settlement).glob("*.json"))
            if len(receipts) == 1:
                receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
                raw_path = (
                    corpus_root / "raw" / settlement / f"{receipt['sha256']}.csv"
                )
                if raw_path.is_file() and _sha256_file(raw_path) == receipt["sha256"]:
                    entries.append(
                        {
                            **receipt,
                            "raw_path": raw_path.relative_to(ROOT).as_posix(),
                            "receipt_path": receipts[0].relative_to(ROOT).as_posix(),
                        }
                    )
                    continue
        content, headers = _download(url, timeout)
        parsed = parse_file(content, protocol["required_columns"])
        if parsed.settlement_date != filename_date.isoformat():
            raise ValueError(f"filename/content date mismatch: {url}")
        digest = _sha256_bytes(content)
        raw_path, receipt_path, created = _write_version(
            corpus_root,
            parsed,
            content,
            digest,
            url,
            headers,
            retrieved_at,
        )
        new_versions += int(created)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        entries.append(
            {
                **receipt,
                "raw_path": raw_path.relative_to(ROOT).as_posix(),
                "receipt_path": receipt_path.relative_to(ROOT).as_posix(),
            }
        )
        time.sleep(0.25)
        if index % 20 == 0 or index == len(urls):
            print(f"collected {index}/{len(urls)} official files", flush=True)
    entries.sort(key=lambda item: (item["settlement_date"], item["sha256"]))
    versions_by_date: dict[str, int] = {}
    for entry in entries:
        versions_by_date[entry["settlement_date"]] = (
            versions_by_date.get(entry["settlement_date"], 0) + 1
        )
    manifest = {
        "manifest_version": "FINRA_SHORT_INTEREST_IMMUTABLE_CENSUS_V1",
        "protocol_path": protocol_path.relative_to(ROOT).as_posix(),
        "protocol_sha256": _sha256_file(protocol_path),
        "created_at_utc": retrieved_at,
        "research_tier": protocol["research_tier"],
        "allowed_research_role": protocol["authority"]["allowed_research_role"],
        "file_count": len(entries),
        "settlement_date_count": len(versions_by_date),
        "first_settlement_date": entries[0]["settlement_date"],
        "last_settlement_date": entries[-1]["settlement_date"],
        "total_bytes": sum(entry["bytes"] for entry in entries),
        "total_rows": sum(entry["row_count"] for entry in entries),
        "revision_flag_rows": sum(entry["revision_flag_rows"] for entry in entries),
        "settlement_dates_with_multiple_local_versions": sorted(
            day for day, count in versions_by_date.items() if count > 1
        ),
        "new_versions_this_run": new_versions,
        "source_revision_limitation": protocol["immutable_storage"][
            "source_revision_limitation"
        ],
        "publication_date_policy": protocol["point_in_time_policy"],
        "entries": entries,
        "authority": protocol["authority"],
    }
    serialized = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    (corpus_root / "manifest.json").write_text(serialized, encoding="utf-8")
    tracked_manifest_path.write_text(serialized, encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    parser.add_argument("--manifest", type=Path, default=TRACKED_MANIFEST)
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()
    result = collect(args.protocol, args.manifest, args.timeout)
    print(json.dumps({
        "file_count": result["file_count"],
        "settlement_date_count": result["settlement_date_count"],
        "first_settlement_date": result["first_settlement_date"],
        "last_settlement_date": result["last_settlement_date"],
        "total_bytes": result["total_bytes"],
        "total_rows": result["total_rows"],
        "new_versions_this_run": result["new_versions_this_run"],
    }, indent=2))


if __name__ == "__main__":
    main()
