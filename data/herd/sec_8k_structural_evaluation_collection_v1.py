"""독립 구조적 표지 평가용 SEC primary document를 불변 snapshot으로 수집한다."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from herd.sec_master_index import resolve_user_agent


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_suffix(".json")
FIELDS = [
    "evaluation_id",
    "event_id",
    "accession_number",
    "cik",
    "filing_date",
    "matched_items",
    "primary_document_url",
    "source_sha256",
    "source_bytes",
    "collection_status",
]


class Sec8KStructuralEvaluationCollectionError(RuntimeError):
    """수집 계약·원문 bytes·권한 경계가 바뀌면 발생한다."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise Sec8KStructuralEvaluationCollectionError(
            f"path escapes repository: {relative}"
        )
    return path


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _locked_paths(protocol: dict[str, Any]) -> dict[str, Path]:
    paths = {}
    for item in protocol["locked_inputs"]:
        path = _rooted(item["path"])
        if not path.is_file() or _sha256(path) != item["sha256"]:
            raise Sec8KStructuralEvaluationCollectionError(
                f"locked input changed: {item['path']}"
            )
        paths[item["role"]] = path
    return paths


def select_queue(protocol: dict[str, Any]) -> list[dict[str, str]]:
    expected_authority = {
        "identity_promotion_allowed": False,
        "price_outcomes_opened": False,
        "direction_hypothesis_allowed": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
    }
    if (
        protocol.get("status") != "LOCKED_BEFORE_INDEPENDENT_SOURCE_COLLECTION"
        or protocol.get("authority") != expected_authority
    ):
        raise Sec8KStructuralEvaluationCollectionError(
            "collection protocol is not fail-closed"
        )
    paths = _locked_paths(protocol)
    queue_report = json.loads(
        paths["EVALUATION_QUEUE_REPORT"].read_text(encoding="utf-8")
    )
    if (
        queue_report.get("status") != "INDEPENDENT_STRUCTURAL_EVALUATION_QUEUE_READY"
        or queue_report.get("canonical_symbols_exposed") != 0
        or queue_report.get("price_outcomes_opened") is not False
    ):
        raise Sec8KStructuralEvaluationCollectionError(
            "evaluation queue is not source-collection ready"
        )
    rows = _read_csv(paths["EVALUATION_QUEUE"])
    config = protocol["collection"]
    if len(rows) != config["expected_documents"]:
        raise Sec8KStructuralEvaluationCollectionError("queue count changed")
    if any(
        urlparse(row["primary_document_url"]).hostname != config["allowed_host"]
        for row in rows
    ):
        raise Sec8KStructuralEvaluationCollectionError("queue contains non-SEC URL")
    return rows


def _download(session: requests.Session, url: str, config: dict[str, Any]) -> bytes:
    last_error: Exception | None = None
    for attempt in range(config["maximum_attempts"]):
        try:
            response = session.get(url, timeout=config["timeout_seconds"])
            response.raise_for_status()
            content = response.content
            if not content or len(content) > config["maximum_document_bytes"]:
                raise Sec8KStructuralEvaluationCollectionError(
                    "SEC document size outside allowed bounds"
                )
            return content
        except (requests.RequestException, Sec8KStructuralEvaluationCollectionError) as error:
            last_error = error
            if attempt + 1 < config["maximum_attempts"]:
                time.sleep(config["delay_seconds"] * (2 ** attempt))
    raise Sec8KStructuralEvaluationCollectionError(str(last_error))


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _validate_existing(snapshot: Path, expected: int) -> tuple[list[dict[str, str]], dict[str, Any]]:
    index = snapshot / "index.csv"
    manifest_path = snapshot / "manifest.json"
    if not index.is_file() or not manifest_path.is_file():
        raise Sec8KStructuralEvaluationCollectionError("existing snapshot is incomplete")
    rows = _read_csv(index)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if len(rows) != expected or manifest.get("documents") != expected:
        raise Sec8KStructuralEvaluationCollectionError("snapshot count changed")
    for item in manifest["files"]:
        path = snapshot / item["path"]
        if not path.is_file() or path.stat().st_size != item["bytes"] or _sha256(path) != item["sha256"]:
            raise Sec8KStructuralEvaluationCollectionError(
                f"snapshot file changed: {item['path']}"
            )
    return rows, manifest


def collect(protocol: dict[str, Any], user_agent: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    queue = select_queue(protocol)
    config = protocol["collection"]
    snapshot = _rooted(config["output_root"]) / config["snapshot_id"]
    if snapshot.exists():
        return _validate_existing(snapshot, len(queue))
    temp = snapshot.parent / f".{snapshot.name}.tmp-{uuid.uuid4().hex}"
    raw = temp / "raw"
    raw.mkdir(parents=True, exist_ok=False)
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"})
    rows = []
    try:
        for position, source in enumerate(queue, start=1):
            content = _download(session, source["primary_document_url"], config)
            (raw / f"{source['accession_number']}.html").write_bytes(content)
            rows.append({
                **{field: source[field] for field in FIELDS[:7]},
                "source_sha256": _sha256_bytes(content),
                "source_bytes": str(len(content)),
                "collection_status": "COLLECTED",
            })
            if position < len(queue):
                time.sleep(config["delay_seconds"])
        _write_csv(temp / "index.csv", rows)
        files = [
            {
                "path": f"raw/{row['accession_number']}.html",
                "bytes": int(row["source_bytes"]),
                "sha256": row["source_sha256"],
            }
            for row in rows
        ]
        manifest = {
            "format_version": protocol["protocol_version"],
            "snapshot_id": config["snapshot_id"],
            "created_at": datetime.now(UTC).isoformat(),
            "protocol_sha256": _sha256(PROTOCOL),
            "documents": len(rows),
            "files": files,
            "canonical_symbols_exposed": 0,
            "price_outcomes_opened": False,
        }
        (temp / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temp.rename(snapshot)
        return rows, manifest
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise


def run() -> dict[str, Any]:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    rows, manifest = collect(protocol, resolve_user_agent(ROOT / ".env"))
    config = protocol["collection"]
    snapshot = _rooted(config["output_root"]) / config["snapshot_id"]
    report = {
        "report_version": protocol["protocol_version"],
        "status": "INDEPENDENT_PRIMARY_DOCUMENTS_COLLECTED",
        "snapshot_id": manifest["snapshot_id"],
        "snapshot_manifest_sha256": _sha256(snapshot / "manifest.json"),
        "collected_documents": len(rows),
        "collected_issuers": len({row["cik"] for row in rows}),
        "failed_documents": 0,
        "canonical_symbols_exposed": 0,
        "identity_promotion_allowed": False,
        "price_outcomes_opened": False,
        "direction_hypothesis_allowed": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
        "next_stage": protocol["next_stage"],
    }
    index_path = _rooted(protocol["outputs"]["index"])
    _write_csv(index_path, rows)
    report["index_path"] = protocol["outputs"]["index"]
    report["index_sha256"] = _sha256(index_path)
    report_path = _rooted(protocol["outputs"]["report"])
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
