"""SEC 공식 Form 13F 구조화 ZIP을 중단 후 재개 가능한 원본으로 고정한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from herd.sec_master_index import resolve_user_agent


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "data/herd/sec_13f_crowding_protocol_v1.json"
DEFAULT_OUTPUT_ROOT = ROOT / "data/reference/sec"
DEFAULT_SNAPSHOT_ID = "sec-13f-bulk-2013q2-2026m05-v1"
DEFAULT_REPORT = ROOT / "data/reports/sec_13f_bulk_v1.json"
LANDING_PAGE = "https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets"
EARLIEST_ARCHIVE = "2013q2_form13f.zip"
LATEST_ARCHIVE = "01mar2026-31may2026_form13f.zip"
REQUIRED_TABLES = {"SUBMISSION.TSV", "INFOTABLE.TSV", "COVERPAGE.TSV"}


class Sec13fBulkError(RuntimeError):
    """공식 원본 목록·ZIP·manifest 불일치 시 발생한다."""


class _ZipLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href and href.lower().endswith("_form13f.zip"):
            self.links.append(href)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _contract(path: Path = PROTOCOL) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        payload.get("protocol_version") != "SEC_13F_CROWDING_PROTOCOL_V1"
        or payload.get("status") != "LOCKED_BEFORE_13F_COLLECTION_AND_PRICE_OUTCOMES"
    ):
        raise Sec13fBulkError("13F crowding protocol is not locked")
    if payload["point_in_time_contract"]["future_price_or_return_access_during_collection"]:
        raise Sec13fBulkError("13F collection cannot access price outcomes")
    return payload


def discover_archives(html: bytes) -> list[dict[str, str]]:
    parser = _ZipLinkParser()
    parser.feed(html.decode("utf-8", errors="replace"))
    unique: dict[str, str] = {}
    for href in parser.links:
        url = urljoin(LANDING_PAGE, href)
        if urlparse(url).hostname != "www.sec.gov":
            raise Sec13fBulkError(f"non-SEC archive URL: {url}")
        filename = Path(urlparse(url).path).name
        unique[filename] = url
    names = list(unique)
    if EARLIEST_ARCHIVE not in names or LATEST_ARCHIVE not in names:
        raise Sec13fBulkError("official archive boundary not found")
    # SEC 페이지는 최신 순이다. 잠근 최신 파일부터 최초 파일까지의 구간만 쓴다.
    latest_index = names.index(LATEST_ARCHIVE)
    earliest_index = names.index(EARLIEST_ARCHIVE)
    if latest_index > earliest_index:
        raise Sec13fBulkError("official archive order changed")
    selected = names[latest_index : earliest_index + 1]
    if len(selected) < 50:
        raise Sec13fBulkError(f"unexpectedly short archive history: {len(selected)}")
    return [{"filename": name, "url": unique[name]} for name in reversed(selected)]


def _zip_tables(path: Path) -> set[str]:
    try:
        with zipfile.ZipFile(path) as archive:
            bad = archive.testzip()
            if bad:
                raise Sec13fBulkError(f"corrupt ZIP member: {bad}")
            return {Path(name).name.upper() for name in archive.namelist()}
    except zipfile.BadZipFile as error:
        raise Sec13fBulkError(f"invalid ZIP: {path}") from error


def validate_zip(path: Path) -> set[str]:
    tables = _zip_tables(path)
    missing = REQUIRED_TABLES - tables
    if missing:
        raise Sec13fBulkError(f"13F ZIP missing tables: {sorted(missing)}")
    return tables


def _write_response(response: Any, destination: Path) -> None:
    with destination.open("wb") as stream:
        if hasattr(response, "iter_content"):
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    stream.write(chunk)
        else:
            stream.write(response.content)


def collect(
    output_root: Path,
    snapshot_id: str,
    *,
    protocol_path: Path = PROTOCOL,
    user_agent: str,
    session: requests.Session | None = None,
    delay_seconds: float = 0.15,
) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,100}", snapshot_id):
        raise Sec13fBulkError("unsafe snapshot id")
    _contract(protocol_path)
    snapshot = output_root / snapshot_id
    raw = snapshot / "raw"
    manifest_path = snapshot / "manifest.json"
    state_path = snapshot / "download_state.json"
    if manifest_path.is_file():
        verify(snapshot, protocol_path=protocol_path)
        return snapshot
    raw.mkdir(parents=True, exist_ok=True)

    client = session or requests.Session()
    client.headers.update(
        {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
        }
    )
    landing_response = client.get(LANDING_PAGE, timeout=120)
    landing_response.raise_for_status()
    landing_html = landing_response.content
    archives = discover_archives(landing_html)
    state = (
        json.loads(state_path.read_text(encoding="utf-8"))
        if state_path.is_file()
        else {
            "format_version": "herd-sec-13f-bulk-download-v1",
            "snapshot_id": snapshot_id,
            "protocol_sha256": sha256(protocol_path),
            "landing_page_sha256": sha256_bytes(landing_html),
            "archives": {},
        }
    )
    if state.get("protocol_sha256") != sha256(protocol_path):
        raise Sec13fBulkError("download state protocol hash mismatch")
    if state.get("landing_page_sha256") != sha256_bytes(landing_html):
        raise Sec13fBulkError("official landing page changed during resumed download")

    for item in archives:
        filename = item["filename"]
        target = raw / filename
        recorded = state["archives"].get(filename)
        if recorded and target.is_file() and sha256(target) == recorded["sha256"]:
            validate_zip(target)
            continue
        temporary = target.with_suffix(".zip.part")
        response = client.get(item["url"], timeout=300, stream=True)
        response.raise_for_status()
        _write_response(response, temporary)
        tables = validate_zip(temporary)
        temporary.replace(target)
        state["archives"][filename] = {
            "url": item["url"],
            "path": f"raw/{filename}",
            "bytes": target.stat().st_size,
            "sha256": sha256(target),
            "tables": sorted(tables),
        }
        state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if session is None:
            print(
                f"[13F] {len(state['archives'])}/{len(archives)} "
                f"{filename} {target.stat().st_size:,} bytes",
                flush=True,
            )
            time.sleep(delay_seconds)

    entries = [state["archives"][item["filename"]] | {
        "filename": item["filename"]
    } for item in archives]
    manifest = {
        "format_version": "herd-sec-13f-bulk-download-v1",
        "snapshot_id": snapshot_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": sha256(protocol_path),
        "source_landing_page": LANDING_PAGE,
        "landing_page_sha256": sha256_bytes(landing_html),
        "earliest_archive": EARLIEST_ARCHIVE,
        "latest_archive": LATEST_ARCHIVE,
        "archive_count": len(entries),
        "bytes": sum(int(item["bytes"]) for item in entries),
        "archives": entries,
        "filing_date_is_exact_acceptance_datetime": False,
        "availability_fallback": "NEXT_TRADING_SESSION_AFTER_FILING_DATE",
        "price_outcomes_opened": False,
        "blind_holdout_access": False,
        "operational_action_authority": False,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    state_path.unlink(missing_ok=True)
    verify(snapshot, protocol_path=protocol_path)
    return snapshot


def verify(snapshot: Path, *, protocol_path: Path = PROTOCOL) -> dict[str, Any]:
    _contract(protocol_path)
    manifest_path = snapshot / "manifest.json"
    if not manifest_path.is_file():
        raise Sec13fBulkError("13F manifest missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("protocol_sha256") != sha256(protocol_path):
        raise Sec13fBulkError("13F manifest protocol hash mismatch")
    if manifest.get("archive_count") != len(manifest.get("archives", [])):
        raise Sec13fBulkError("13F archive count mismatch")
    if manifest.get("archive_count", 0) < 50:
        raise Sec13fBulkError("13F archive history is incomplete")
    total_bytes = 0
    for item in manifest["archives"]:
        path = snapshot / item["path"]
        if not path.is_file() or sha256(path) != item["sha256"]:
            raise Sec13fBulkError(f"13F archive hash changed: {item['filename']}")
        validate_zip(path)
        total_bytes += path.stat().st_size
    if total_bytes != manifest["bytes"]:
        raise Sec13fBulkError("13F byte count mismatch")
    for key in (
        "price_outcomes_opened",
        "blind_holdout_access",
        "operational_action_authority",
    ):
        if manifest.get(key):
            raise Sec13fBulkError(f"13F raw corpus received forbidden authority: {key}")
    return manifest


def build_report(snapshot: Path, *, protocol_path: Path = PROTOCOL) -> dict[str, Any]:
    manifest = verify(snapshot, protocol_path=protocol_path)
    snapshot_path = (
        snapshot.relative_to(ROOT).as_posix()
        if snapshot.is_relative_to(ROOT)
        else snapshot.as_posix()
    )
    return {
        "report_version": "SEC_13F_BULK_V1",
        "status": "OFFICIAL_13F_RAW_CORPUS_HASH_LOCKED",
        "snapshot_path": snapshot_path,
        "manifest_sha256": sha256(snapshot / "manifest.json"),
        "archive_count": manifest["archive_count"],
        "bytes": manifest["bytes"],
        "earliest_archive": manifest["earliest_archive"],
        "latest_archive": manifest["latest_archive"],
        "exact_acceptance_datetime_ready": False,
        "availability_fallback": manifest["availability_fallback"],
        "price_outcomes_opened": False,
        "direction_hypothesis_executed": False,
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
        "next_step": "BUILD_TIME_VALID_SECURITY_IDENTIFIER_LEDGER",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--snapshot-id", default=DEFAULT_SNAPSHOT_ID)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    snapshot = args.output_root / args.snapshot_id
    if args.verify_only:
        verify(snapshot)
    else:
        collect(
            args.output_root,
            args.snapshot_id,
            user_agent=resolve_user_agent(args.env_file),
        )
    report = build_report(snapshot)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
