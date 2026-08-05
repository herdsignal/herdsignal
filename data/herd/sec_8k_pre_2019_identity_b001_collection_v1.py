"""B001 issuer의 SEC submissions metadata를 불변 snapshot으로 수집한다."""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from herd.sec_master_index import resolve_user_agent

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_suffix(".json")


class Sec8KPre2019IdentityB001CollectionV1Error(RuntimeError):
    pass


def _sha_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _path(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise Sec8KPre2019IdentityB001CollectionV1Error("path escapes repository")
    return path


def _locked(protocol: dict[str, Any]) -> dict[str, Path]:
    paths = {}
    for item in protocol["locked_inputs"]:
        path = _path(item["path"])
        if not path.is_file() or _sha(path) != item["sha256"]:
            raise Sec8KPre2019IdentityB001CollectionV1Error(f"locked input changed: {item['path']}")
        paths[item["role"]] = path
    return paths


def _download(session: requests.Session, url: str, config: dict[str, Any]) -> bytes:
    last_error: Exception | None = None
    for attempt in range(int(config["maximum_attempts"])):
        try:
            response = session.get(url, timeout=float(config["timeout_seconds"])); response.raise_for_status()
            content = response.content
            if not content or len(content) > int(config["maximum_document_bytes"]):
                raise Sec8KPre2019IdentityB001CollectionV1Error("SEC metadata size outside allowed bounds")
            return content
        except (requests.RequestException, Sec8KPre2019IdentityB001CollectionV1Error) as error:
            last_error = error
            if attempt + 1 < int(config["maximum_attempts"]):
                time.sleep(float(config["delay_seconds"]) * (2 ** attempt))
    raise Sec8KPre2019IdentityB001CollectionV1Error(str(last_error))


def _queue(protocol: dict[str, Any], paths: dict[str, Path]) -> list[dict[str, str]]:
    report = json.loads(paths["QUEUE_REPORT"].read_text(encoding="utf-8"))
    if report.get("status") != "PRE_2019_IDENTITY_EVIDENCE_QUEUE_READY":
        raise Sec8KPre2019IdentityB001CollectionV1Error("issuer queue is not ready")
    with paths["ISSUER_QUEUE"].open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row["batch_id"] == protocol["selection"]["batch_id"]]
    if len(rows) != protocol["selection"]["issuers"] or sum(int(row["event_count"]) for row in rows) != protocol["selection"]["events"]:
        raise Sec8KPre2019IdentityB001CollectionV1Error("B001 population changed")
    return rows


def _filing_rows(payload: dict[str, Any]) -> list[dict[str, str]]:
    recent = payload.get("filings", {}).get("recent", {})
    keys = ("accessionNumber", "filingDate", "form", "primaryDocument")
    size = len(recent.get("accessionNumber", []))
    return [{key: recent.get(key, [""] * size)[index] for key in keys} for index in range(size)]


def collect(protocol_path: Path = PROTOCOL) -> tuple[list[dict[str, str]], dict[str, Any]]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8")); authority = protocol.get("authority", {})
    if protocol.get("status") != "LOCKED_BATCH_BEFORE_SEC_SUBMISSIONS_COLLECTION" or authority.get("metadata_is_identity_proof") is not False or authority.get("automatic_identity_promotion") is not False or authority.get("operational_action_ratio") != 0.0:
        raise Sec8KPre2019IdentityB001CollectionV1Error("collection is not fail-closed")
    paths = _locked(protocol); queue = _queue(protocol, paths); config = protocol["collection"]
    snapshot = _path(config["output_root"]) / config["snapshot_id"]
    if snapshot.exists():
        manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
        with (snapshot / "index.csv").open(newline="", encoding="utf-8") as handle: rows = list(csv.DictReader(handle))
        for item in manifest["files"]:
            path = snapshot / item["path"]
            if not path.is_file() or _sha(path) != item["sha256"]: raise Sec8KPre2019IdentityB001CollectionV1Error("snapshot changed")
        return rows, manifest

    temp = snapshot.parent / f".{config['snapshot_id']}.tmp-{uuid.uuid4().hex}"; raw = temp / "raw"; raw.mkdir(parents=True)
    session = requests.Session(); session.headers.update({"User-Agent": resolve_user_agent(ROOT / ".env"), "Accept-Encoding": "gzip, deflate"})
    rows = []; files = []
    try:
        for issuer_position, issuer in enumerate(queue):
            cik = issuer["cik"]; root_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
            content = _download(session, root_url, config); root_name = f"raw/CIK{cik}.json"; (temp / root_name).write_bytes(content)
            payload = json.loads(content); all_filings = _filing_rows(payload); files.append({"path": root_name, "bytes": len(content), "sha256": _sha_bytes(content)})
            historical_files = payload.get("filings", {}).get("files", [])
            for old in historical_files:
                name = old["name"]; old_content = _download(session, f"https://data.sec.gov/submissions/{name}", config)
                relative = f"raw/{name}"; (temp / relative).write_bytes(old_content); files.append({"path": relative, "bytes": len(old_content), "sha256": _sha_bytes(old_content)})
                all_filings.extend(_filing_rows({"filings": {"recent": json.loads(old_content)}}))
                time.sleep(float(config["delay_seconds"]))
            eligible = [row for row in all_filings if row["form"] in {"10-K", "10-K/A", "10-Q", "10-Q/A"} and row["filingDate"] <= issuer["last_anchor_date"] and row["filingDate"] >= issuer["first_event_date"]]
            rows.append({"queue_id": issuer["queue_id"], "batch_id": issuer["batch_id"], "cik": cik, "event_count": issuer["event_count"], "first_event_date": issuer["first_event_date"], "last_event_date": issuer["last_event_date"], "anchor_symbols": issuer["anchor_symbols"], "sec_entity_name": payload.get("name", ""), "submission_files": str(1 + len(historical_files)), "total_filing_metadata_rows": str(len(all_filings)), "candidate_periodic_filings": str(len(eligible)), "collection_status": "SEC_SUBMISSIONS_METADATA_COLLECTED", "review_status": "PRIMARY_DOCUMENT_SELECTION_REQUIRED", "promotion_status": "BLOCKED"})
            if issuer_position + 1 < len(queue): time.sleep(float(config["delay_seconds"]))
        fields = list(rows[0]);
        with (temp / "index.csv").open("w", newline="", encoding="utf-8") as handle: writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n"); writer.writeheader(); writer.writerows(rows)
        manifest = {"format_version": protocol["protocol_version"], "snapshot_id": config["snapshot_id"], "created_at": datetime.now(timezone.utc).isoformat(), "issuers": len(rows), "files": files, "metadata_is_identity_proof": False, "price_outcomes_opened": False}
        (temp / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); temp.rename(snapshot)
        return rows, manifest
    except Exception:
        shutil.rmtree(temp, ignore_errors=True); raise


def run() -> dict[str, Any]:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8")); rows, manifest = collect(); index = _path(protocol["outputs"]["index"])
    with index.open("w", newline="", encoding="utf-8") as handle: writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n"); writer.writeheader(); writer.writerows(rows)
    report = {"report_version": protocol["protocol_version"], "status": "B001_SEC_SUBMISSIONS_METADATA_COLLECTED", "batch_id": "B001", "issuers": len(rows), "events": sum(int(row["event_count"]) for row in rows), "snapshot_id": manifest["snapshot_id"], "snapshot_files": len(manifest["files"]), "candidate_periodic_filings": sum(int(row["candidate_periodic_filings"]) for row in rows), "metadata_is_identity_proof": False, "automatic_identity_promotion": False, "price_outcomes_opened": False, "direction_hypothesis_allowed": False, "blind_holdout_access": False, "operational_action_ratio": 0.0, "next_stage": "SELECT_B001_PERIODIC_PRIMARY_DOCUMENTS_FOR_IDENTITY_REVIEW", "index_path": protocol["outputs"]["index"], "index_sha256": _sha(index)}
    _path(protocol["outputs"]["report"]).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); return report


if __name__ == "__main__": print(json.dumps(run(), ensure_ascii=False, indent=2))
