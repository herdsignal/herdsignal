"""Collect a hashed first wave of SEC 8-K cover documents for identity review."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from herd.sec_master_index import resolve_user_agent
from herd.sec_trading_symbol_evidence import extract_trading_symbols


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json")
VERSION = "SEC_8K_IDENTITY_PRIMARY_DOCUMENT_COLLECTION_V1"
FIELDNAMES = [
    "queue_id",
    "priority",
    "event_id",
    "cik",
    "accession_number",
    "filing_date",
    "matched_items",
    "prior_identity_status",
    "primary_document_url",
    "source_sha256",
    "source_bytes",
    "extracted_symbols",
    "extraction_status",
    "adjudication_status",
]


class Sec8KIdentityCollectionError(RuntimeError):
    """Raised when collection inputs, source bytes, or authority drift."""


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise Sec8KIdentityCollectionError(f"path escapes repository: {relative}")
    return path


def _locked_paths(protocol: dict[str, Any]) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for specification in protocol["locked_inputs"]:
        path = _rooted(specification["path"])
        if not path.is_file() or _sha256(path) != specification["sha256"]:
            raise Sec8KIdentityCollectionError(f"locked input changed: {specification['path']}")
        paths[specification["role"]] = path
    return paths


def select_queue(protocol: dict[str, Any]) -> list[dict[str, str]]:
    paths = _locked_paths(protocol)
    queue_report = json.loads(paths["IDENTITY_QUEUE_REPORT"].read_text(encoding="utf-8"))
    if (
        queue_report.get("price_outcomes_opened") is not False
        or queue_report.get("direction_hypothesis_allowed") is not False
        or queue_report.get("queue_events") != 762
    ):
        raise Sec8KIdentityCollectionError("identity queue is not result-blind")
    priorities = set(protocol["selection"]["priorities"])
    with paths["IDENTITY_QUEUE"].open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row["priority"] in priorities]
    if len(rows) != protocol["selection"]["expected_documents"]:
        raise Sec8KIdentityCollectionError("first-wave queue size changed")
    if len({row["queue_id"] for row in rows}) != len(rows):
        raise Sec8KIdentityCollectionError("duplicate first-wave queue id")
    allowed_host = protocol["collection"]["allowed_host"]
    if any(urlparse(row["primary_document_url"]).hostname != allowed_host for row in rows):
        raise Sec8KIdentityCollectionError("queue contains a non-SEC URL")
    return rows


def _download(session: requests.Session, url: str, protocol: dict[str, Any]) -> bytes:
    config = protocol["collection"]
    last_error: Exception | None = None
    for attempt in range(int(config["maximum_attempts"])):
        try:
            response = session.get(url, timeout=float(config["timeout_seconds"]))
            response.raise_for_status()
            content = response.content
            if not content or len(content) > int(config["maximum_document_bytes"]):
                raise Sec8KIdentityCollectionError("SEC document size outside allowed bounds")
            return content
        except (requests.RequestException, Sec8KIdentityCollectionError) as error:
            last_error = error
            if attempt + 1 < int(config["maximum_attempts"]):
                time.sleep(float(config["delay_seconds"]) * (2 ** attempt))
    raise Sec8KIdentityCollectionError(str(last_error))


def _normalize_row(source: dict[str, str], content: bytes) -> dict[str, str]:
    symbols = extract_trading_symbols(content)
    return {
        "queue_id": source["queue_id"],
        "priority": source["priority"],
        "event_id": source["event_id"],
        "cik": source["cik"],
        "accession_number": source["accession_number"],
        "filing_date": source["filing_date"],
        "matched_items": source["matched_items"],
        "prior_identity_status": source["prior_identity_status"],
        "primary_document_url": source["primary_document_url"],
        "source_sha256": _sha256_bytes(content),
        "source_bytes": str(len(content)),
        "extracted_symbols": "|".join(symbols),
        "extraction_status": "CANDIDATE_FOUND" if symbols else "NO_CANDIDATE_FOUND",
        "adjudication_status": "PENDING_SOURCE_REVIEW",
    }


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _manifest(snapshot_id: str, rows: list[dict[str, str]], raw: Path) -> dict[str, Any]:
    files = []
    for row in rows:
        relative = f"raw/{row['accession_number']}.html"
        path = raw.parent / relative
        files.append({
            "path": relative,
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        })
    return {
        "format_version": VERSION,
        "snapshot_id": snapshot_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": _sha256(PROTOCOL_PATH),
        "documents": len(rows),
        "files": files,
        "price_outcomes_opened": False,
    }


def _validate_snapshot(snapshot: Path, expected_documents: int) -> tuple[list[dict[str, str]], dict[str, Any]]:
    manifest_path = snapshot / "manifest.json"
    index_path = snapshot / "index.csv"
    if not manifest_path.is_file() or not index_path.is_file():
        raise Sec8KIdentityCollectionError("existing snapshot is incomplete")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    with index_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if manifest.get("documents") != expected_documents or len(rows) != expected_documents:
        raise Sec8KIdentityCollectionError("existing snapshot count changed")
    for item in manifest["files"]:
        path = snapshot / item["path"]
        if (
            not path.is_file()
            or path.stat().st_size != item["bytes"]
            or _sha256(path) != item["sha256"]
        ):
            raise Sec8KIdentityCollectionError(f"snapshot file changed: {item['path']}")
    return rows, manifest


def collect(protocol: dict[str, Any], user_agent: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    if (
        protocol.get("protocol_version") != VERSION
        or protocol.get("status") != "LOCKED_FIRST_WAVE_BEFORE_COLLECTION"
        or protocol.get("authority")
        != {
            "price_outcomes_opened": False,
            "identity_promotion_allowed": False,
            "direction_hypothesis_allowed": False,
            "blind_holdout_access": False,
            "operational_action_ratio": 0.0,
        }
    ):
        raise Sec8KIdentityCollectionError("collection protocol is not fail-closed")
    queue = select_queue(protocol)
    config = protocol["collection"]
    output_root = _rooted(config["output_root"])
    snapshot = output_root / config["snapshot_id"]
    if snapshot.exists():
        return _validate_snapshot(snapshot, len(queue))

    temp = output_root / f".{config['snapshot_id']}.tmp-{uuid.uuid4().hex}"
    raw = temp / "raw"
    raw.mkdir(parents=True, exist_ok=False)
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"})
    rows: list[dict[str, str]] = []
    try:
        for position, source in enumerate(queue, start=1):
            content = _download(session, source["primary_document_url"], protocol)
            row = _normalize_row(source, content)
            (raw / f"{source['accession_number']}.html").write_bytes(content)
            rows.append(row)
            if position < len(queue):
                time.sleep(float(config["delay_seconds"]))
        _write_csv(temp / "index.csv", rows)
        manifest = _manifest(config["snapshot_id"], rows, raw)
        (temp / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temp.rename(snapshot)
        return rows, manifest
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise


def build_report(
    protocol: dict[str, Any], rows: list[dict[str, str]], manifest: dict[str, Any]
) -> dict[str, Any]:
    counts = Counter(row["extraction_status"] for row in rows)
    return {
        "report_version": VERSION,
        "status": "FIRST_WAVE_COLLECTED_SOURCE_REVIEW_REQUIRED",
        "protocol_sha256": _sha256(PROTOCOL_PATH),
        "snapshot_id": manifest["snapshot_id"],
        "snapshot_manifest_sha256": _sha256(
            _rooted(protocol["collection"]["output_root"])
            / protocol["collection"]["snapshot_id"]
            / "manifest.json"
        ),
        "collected_documents": len(rows),
        "collected_issuers": len({row["cik"] for row in rows}),
        "priority_counts": dict(sorted(Counter(row["priority"] for row in rows).items())),
        "extraction_counts": dict(sorted(counts.items())),
        "candidate_symbol_rows": counts["CANDIDATE_FOUND"],
        "candidate_symbols_promoted": 0,
        "source_review_required": True,
        "price_outcomes_opened": False,
        "direction_hypothesis_allowed": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
        "next_stage": protocol["next_stage_if_complete"],
    }


def run() -> dict[str, Any]:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    user_agent = resolve_user_agent(ROOT / ".env")
    rows, manifest = collect(protocol, user_agent)
    report = build_report(protocol, rows, manifest)
    index_path = _rooted(protocol["output"]["index"])
    report_path = _rooted(protocol["output"]["report"])
    index_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(index_path, rows)
    report["index_path"] = protocol["output"]["index"]
    report["index_sha256"] = _sha256(index_path)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
