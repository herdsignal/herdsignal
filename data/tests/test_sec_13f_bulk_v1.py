import io
import json
import zipfile
from pathlib import Path

import pytest

from herd.sec_13f_bulk_v1 import (
    EARLIEST_ARCHIVE,
    LATEST_ARCHIVE,
    Sec13fBulkError,
    build_report,
    collect,
    discover_archives,
    sha256,
    verify,
)


def _zip_payload() -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("SUBMISSION.tsv", "ACCESSION_NUMBER\tFILING_DATE\n1\t01-JAN-2020\n")
        archive.writestr("COVERPAGE.tsv", "ACCESSION_NUMBER\tISAMENDMENT\n1\t\n")
        archive.writestr("INFOTABLE.tsv", "ACCESSION_NUMBER\tCUSIP\n1\t000000001\n")
    return stream.getvalue()


def _landing() -> bytes:
    names = [EARLIEST_ARCHIVE]
    names.extend(f"{year}q{quarter}_form13f.zip" for year in range(2014, 2026) for quarter in range(1, 5))
    names.append(LATEST_ARCHIVE)
    links = "".join(
        f'<a href="/files/structureddata/data/form-13f-data-sets/{name}">{name}</a>'
        for name in reversed(names)
    )
    return links.encode()


class _Response:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        assert chunk_size == 1024 * 1024
        yield self.content


class _Session:
    def __init__(self):
        self.headers = {}
        self.calls = 0

    def get(self, url, timeout, stream=False):
        self.calls += 1
        if url.endswith("form-13f-data-sets"):
            assert timeout == 120
            return _Response(_landing())
        assert timeout == 300
        assert stream is True
        return _Response(_zip_payload())


def test_discovery_keeps_pinned_official_boundaries():
    archives = discover_archives(_landing())
    assert archives[0]["filename"] == EARLIEST_ARCHIVE
    assert archives[-1]["filename"] == LATEST_ARCHIVE
    assert len(archives) >= 50
    assert all(item["url"].startswith("https://www.sec.gov/") for item in archives)


def test_discovery_rejects_incomplete_history():
    html = (
        f'<a href="/{LATEST_ARCHIVE}">latest</a>'
        f'<a href="/{EARLIEST_ARCHIVE}">earliest</a>'
    ).encode()
    with pytest.raises(Sec13fBulkError):
        discover_archives(html)


def test_collection_is_resumable_and_hash_verified(tmp_path):
    session = _Session()
    snapshot = collect(
        tmp_path,
        "fixture-13f",
        user_agent="HerdSignal fixture fixture@example.com",
        session=session,
    )
    manifest = verify(snapshot)
    assert manifest["archive_count"] >= 50
    assert manifest["filing_date_is_exact_acceptance_datetime"] is False
    assert manifest["availability_fallback"] == "NEXT_TRADING_SESSION_AFTER_FILING_DATE"
    first_calls = session.calls
    assert collect(
        tmp_path,
        "fixture-13f",
        user_agent="HerdSignal fixture fixture@example.com",
        session=session,
    ) == snapshot
    assert session.calls == first_calls
    report = build_report(snapshot)
    assert report["status"] == "OFFICIAL_13F_RAW_CORPUS_HASH_LOCKED"
    assert report["exact_acceptance_datetime_ready"] is False
    assert report["operational_action_ratio"] == 0.0


def test_verification_rejects_modified_archive(tmp_path):
    snapshot = collect(
        tmp_path,
        "fixture-13f",
        user_agent="HerdSignal fixture fixture@example.com",
        session=_Session(),
    )
    manifest = json.loads((snapshot / "manifest.json").read_text())
    path = snapshot / manifest["archives"][0]["path"]
    original = sha256(path)
    path.write_bytes(path.read_bytes() + b"changed")
    assert sha256(path) != original
    with pytest.raises(Sec13fBulkError):
        verify(snapshot)
