"""선정된 issuer의 SEC periodic cover 원문만 수집하고 ticker 앵커를 고정한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import requests
from lxml import html

from herd.sec_master_index import resolve_user_agent
from herd.sec_time_valid_ticker_cik_ledger_v2 import canonical_symbol
from herd.sec_trading_symbol_evidence import extract_trading_symbols


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_name("sec_cover_page_targeted_ledger_v1.json")
SNAPSHOT_ID = "sec-cover-page-targeted-v1-202106-202606-20260723"
SNAPSHOT_ROOT = ROOT / "data/reference/sec"
SOURCE_REPORT = ROOT / "data/reports/sec_cover_page_targeted_source_v1.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SUBMISSION_FILE_URL = "https://data.sec.gov/submissions/{name}"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"


class SecCoverSourceError(RuntimeError):
    pass


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _root_path(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise SecCoverSourceError(f"path escapes repository: {relative}")
    return path


def verify_prerequisites(protocol: dict) -> None:
    for item in protocol["prerequisites"]:
        path = _root_path(item["path"])
        if sha256(path) != item["sha256"]:
            raise SecCoverSourceError(f"locked prerequisite changed: {item['path']}")


def extract_entity_ciks(content: bytes) -> list[str]:
    ciks = set()
    try:
        document = html.fromstring(content)
        for element in document.xpath("//*[@name]"):
            if not str(element.get("name", "")).lower().endswith(
                "entitycentralindexkey"
            ):
                continue
            value = re.sub(r"\D", "", " ".join(element.text_content().split()))
            if value:
                ciks.add(value.zfill(10))
    except (ValueError, html.etree.ParserError):
        pass
    return sorted(ciks)


def _filing_rows(payload: dict) -> list[dict]:
    required = {
        "accessionNumber",
        "filingDate",
        "acceptanceDateTime",
        "form",
        "primaryDocument",
    }
    if not required.issubset(payload):
        raise SecCoverSourceError("incomplete SEC submissions filing schema")
    length = len(payload["accessionNumber"])
    if any(len(payload[field]) != length for field in required):
        raise SecCoverSourceError("misaligned SEC submissions columns")
    return [
        {
            "accession_number": payload["accessionNumber"][position],
            "filing_date": payload["filingDate"][position],
            "accepted_at": payload["acceptanceDateTime"][position],
            "form": payload["form"][position],
            "primary_document": payload["primaryDocument"][position],
        }
        for position in range(length)
    ]


def _get(session: requests.Session, url: str) -> bytes:
    response = session.get(url, timeout=90)
    response.raise_for_status()
    return response.content


def _download_json(
    session: requests.Session,
    url: str,
    destination: Path,
) -> dict:
    content = _get(session, url)
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as error:
        raise SecCoverSourceError(f"invalid SEC JSON: {url}") from error
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    return payload


def _selected_filings(
    session: requests.Session,
    cik: str,
    destination: Path,
    protocol: dict,
    delay_seconds: float,
) -> tuple[list[dict], list[dict]]:
    submissions_path = destination / "submissions" / f"CIK{cik}.json"
    payload = _download_json(
        session,
        SUBMISSIONS_URL.format(cik=cik),
        submissions_path,
    )
    if str(payload.get("cik", "")).zfill(10) != cik:
        raise SecCoverSourceError(f"submissions CIK mismatch: {cik}")
    pieces = [{
        "source_url": SUBMISSIONS_URL.format(cik=cik),
        "path": submissions_path,
        "payload": payload["filings"]["recent"],
    }]
    start = protocol["selection_policy"]["target_start"]
    end = protocol["selection_policy"]["target_end"]
    for metadata in payload.get("filings", {}).get("files", []):
        if metadata.get("filingTo", "") < start or metadata.get("filingFrom", "") > end:
            continue
        name = metadata["name"]
        path = destination / "submissions" / name
        time.sleep(delay_seconds)
        supplemental = _download_json(
            session,
            SUBMISSION_FILE_URL.format(name=name),
            path,
        )
        pieces.append({
            "source_url": SUBMISSION_FILE_URL.format(name=name),
            "path": path,
            "payload": supplemental,
        })
    allowed = set(protocol["selection_policy"]["allowed_periodic_forms"])
    filings, sources = {}, []
    for piece in pieces:
        sources.append({
            "url": piece["source_url"],
            "path": piece["path"].relative_to(destination).as_posix(),
            "sha256": sha256(piece["path"]),
            "bytes": piece["path"].stat().st_size,
        })
        for row in _filing_rows(piece["payload"]):
            if (
                row["form"] in allowed
                and start <= row["filing_date"] <= end
                and row["accepted_at"]
                and row["primary_document"]
            ):
                filings[row["accession_number"]] = row
    return sorted(
        filings.values(),
        key=lambda row: (row["filing_date"], row["accession_number"]),
    ), sources


def _target_by_cik(protocol: dict) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for target in protocol["targets"]:
        cik = target["cik"]
        item = result.setdefault(cik, {"symbols": set(), "targets": []})
        item["symbols"].update(target["expected_cover_symbols"])
        item["targets"].append(target["research_ticker"])
    return result


def _archive_primary_document(
    session: requests.Session,
    destination: Path,
    cik: str,
    filing: dict,
) -> tuple[Path, str]:
    accession_key = filing["accession_number"].replace("-", "")
    document = Path(filing["primary_document"]).name
    url = ARCHIVE_URL.format(
        cik=int(cik),
        accession=accession_key,
        document=document,
    )
    content = _get(session, url)
    path = destination / "primary" / cik / accession_key / document
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path, url


def _plain_text(content: bytes) -> str:
    try:
        return " ".join(html.fromstring(content).text_content().split())
    except (ValueError, html.etree.ParserError):
        return " ".join(content.decode("utf-8", errors="ignore").split())


def _collect_identity_events(
    session: requests.Session,
    destination: Path,
    protocol: dict,
    delay_seconds: float,
) -> list[dict]:
    events = []
    for position, event in enumerate(protocol["exact_identity_events"], start=1):
        time.sleep(delay_seconds)
        content = _get(session, event["source_url"])
        text = _plain_text(content).casefold()
        missing = [
            term for term in event["required_terms"]
            if term.casefold() not in text
        ]
        if missing:
            raise SecCoverSourceError(
                f"identity event required terms missing: {missing}"
            )
        suffix = Path(event["source_url"]).suffix or ".html"
        path = destination / "identity-events" / f"event-{position:02d}{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        events.append({
            **event,
            "path": path.relative_to(destination).as_posix(),
            "sha256": sha256_bytes(content),
            "bytes": len(content),
            "required_terms_verified": True,
        })
    return events


def collect(
    *,
    protocol_path: Path = PROTOCOL,
    output_root: Path = SNAPSHOT_ROOT,
    snapshot_id: str = SNAPSHOT_ID,
    source_report_path: Path = SOURCE_REPORT,
    env_file: Path = ROOT / ".env",
    delay_seconds: float = 0.12,
) -> dict:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol["status"] != "LOCKED_BEFORE_SOURCE_COLLECTION":
        raise SecCoverSourceError("source protocol is not locked")
    verify_prerequisites(protocol)
    target = output_root / snapshot_id
    if target.exists():
        raise SecCoverSourceError(f"snapshot already exists: {target}")
    temporary = output_root / f".{snapshot_id}.tmp-{uuid.uuid4().hex}"
    temporary.mkdir(parents=True)
    session = requests.Session()
    session.headers.update({
        "User-Agent": resolve_user_agent(env_file),
        "Accept-Encoding": "gzip, deflate",
    })
    target_by_cik = _target_by_cik(protocol)
    submissions_sources, documents, accepted_anchors = [], [], []
    try:
        for cik, target_info in sorted(target_by_cik.items()):
            filings, sources = _selected_filings(
                session, cik, temporary, protocol, delay_seconds
            )
            submissions_sources.extend(sources)
            expected_by_canonical = {
                canonical_symbol(symbol): symbol
                for symbol in target_info["symbols"]
            }
            for filing in filings:
                time.sleep(delay_seconds)
                path, url = _archive_primary_document(
                    session, temporary, cik, filing
                )
                content = path.read_bytes()
                symbols = extract_trading_symbols(content)
                entity_ciks = extract_entity_ciks(content)
                matched = sorted({
                    expected_by_canonical[canonical_symbol(symbol)]
                    for symbol in symbols
                    if canonical_symbol(symbol) in expected_by_canonical
                })
                cik_match = not entity_ciks or cik in entity_ciks
                status = (
                    "ACCEPTED_COVER_ANCHOR"
                    if matched and cik_match
                    else "QUARANTINED_CIK_MISMATCH"
                    if not cik_match
                    else "NO_EXPECTED_EQUITY_SYMBOL"
                )
                item = {
                    "cik": cik,
                    "research_tickers": sorted(set(target_info["targets"])),
                    **filing,
                    "source_url": url,
                    "path": path.relative_to(temporary).as_posix(),
                    "sha256": sha256_bytes(content),
                    "bytes": len(content),
                    "extracted_symbols": symbols,
                    "extracted_entity_ciks": entity_ciks,
                    "matched_expected_symbols": matched,
                    "status": status,
                }
                documents.append(item)
                for symbol in matched if status == "ACCEPTED_COVER_ANCHOR" else []:
                    accepted_anchors.append({
                        "cik": cik,
                        "symbol": symbol,
                        "canonical_symbol": canonical_symbol(symbol),
                        "filing_date": filing["filing_date"],
                        "accepted_at": filing["accepted_at"],
                        "accession_number": filing["accession_number"],
                        "form": filing["form"],
                        "source_url": url,
                        "document_sha256": item["sha256"],
                    })
        identity_events = _collect_identity_events(
            session, temporary, protocol, delay_seconds
        )
        manifest = {
            "report_version": "SEC_COVER_PAGE_TARGETED_SOURCE_V1",
            "snapshot_id": snapshot_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "protocol_path": protocol_path.relative_to(ROOT).as_posix(),
            "protocol_sha256": sha256(protocol_path),
            "target_cik_count": len(target_by_cik),
            "target_research_tickers": sorted({
                row["research_ticker"] for row in protocol["targets"]
            }),
            "submissions_sources": submissions_sources,
            "documents": documents,
            "identity_events": identity_events,
            "accepted_anchors": accepted_anchors,
            "document_count": len(documents),
            "accepted_document_count": sum(
                row["status"] == "ACCEPTED_COVER_ANCHOR" for row in documents
            ),
            "accepted_anchor_count": len(accepted_anchors),
            "quarantined_document_count": sum(
                row["status"] != "ACCEPTED_COVER_ANCHOR" for row in documents
            ),
            "price_outcomes_opened": False,
            "direction_hypothesis_preregistered": False,
            "herd_formula_change_allowed": False,
            "blind_holdout_access": False,
            "operational_action_authority": False,
            "operational_action_ratio": 0.0,
        }
        manifest_path = temporary / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        output_root.mkdir(parents=True, exist_ok=True)
        temporary.rename(target)
        manifest["snapshot_manifest_sha256"] = sha256(target / "manifest.json")
        manifest["snapshot_path"] = target.relative_to(ROOT).as_posix()
        source_report_path.parent.mkdir(parents=True, exist_ok=True)
        source_report_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return manifest
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    parser.add_argument("--root", type=Path, default=SNAPSHOT_ROOT)
    parser.add_argument("--snapshot-id", default=SNAPSHOT_ID)
    parser.add_argument("--report", type=Path, default=SOURCE_REPORT)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--delay", type=float, default=0.12)
    args = parser.parse_args()
    print(json.dumps(collect(
        protocol_path=args.protocol,
        output_root=args.root,
        snapshot_id=args.snapshot_id,
        source_report_path=args.report,
        env_file=args.env_file,
        delay_seconds=args.delay,
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
