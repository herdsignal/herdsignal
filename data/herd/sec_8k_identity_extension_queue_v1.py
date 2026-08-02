"""Build the SEC primary-document queue for unresolved event identities."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json")
VERSION = "SEC_8K_IDENTITY_EXTENSION_QUEUE_V1"
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
    "collection_status",
    "source_sha256",
    "extracted_symbols",
    "adjudication_status",
]


class Sec8KIdentityQueueError(ValueError):
    """Raised when the locked queue inputs or authority change."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise Sec8KIdentityQueueError(f"path escapes repository: {relative}")
    return path


def _locked_paths(protocol: dict[str, Any]) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for specification in protocol["locked_inputs"]:
        path = _rooted(specification["path"])
        if not path.is_file() or _sha256(path) != specification["sha256"]:
            raise Sec8KIdentityQueueError(f"locked input changed: {specification['path']}")
        paths[specification["role"]] = path
    return paths


def _priority(row: dict[str, str]) -> str:
    if row["identity_status"] == "AMBIGUOUS":
        return "P0_AMBIGUOUS"
    if row["filing_date"] >= "2016-01-01":
        return "P1_TEN_YEAR_WINDOW"
    return "P2_LONG_HISTORY"


def build(protocol: dict[str, Any]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    if (
        protocol.get("protocol_version") != VERSION
        or protocol.get("status") != "LOCKED_AFTER_CORPUS_IDENTITY_FAILURE"
        or protocol.get("authority")
        != {
            "price_outcomes_opened": False,
            "direction_hypothesis_allowed": False,
            "blind_holdout_access": False,
            "operational_action_ratio": 0.0,
        }
    ):
        raise Sec8KIdentityQueueError("identity queue protocol is not fail-closed")
    paths = _locked_paths(protocol)
    corpus_report = json.loads(paths["CORPUS_REPORT"].read_text(encoding="utf-8"))
    if (
        corpus_report.get("identity_linkage_passed") is not False
        or corpus_report.get("next_stage") != "TIME_VALID_TICKER_CIK_LEDGER_EXTENSION_REQUIRED"
        or corpus_report.get("price_outcomes_opened") is not False
    ):
        raise Sec8KIdentityQueueError("corpus does not require identity extension")

    with paths["CORPUS_LEDGER"].open(newline="", encoding="utf-8") as handle:
        unresolved = [
            row for row in csv.DictReader(handle)
            if row["identity_status"] in {"UNMAPPED", "AMBIGUOUS"}
        ]
    expected = protocol["expected_queue"]
    counts = Counter(row["identity_status"] for row in unresolved)
    if (
        counts["UNMAPPED"] != expected["unmapped_events"]
        or counts["AMBIGUOUS"] != expected["ambiguous_events"]
        or len(unresolved) != expected["total_events"]
    ):
        raise Sec8KIdentityQueueError("unresolved identity inventory changed")

    rows: list[dict[str, str]] = []
    for source in unresolved:
        url = source["primary_document_url"]
        if urlparse(url).hostname != protocol["collection_policy"]["allowed_host"]:
            raise Sec8KIdentityQueueError(f"non-SEC source URL: {url}")
        rows.append({
            "queue_id": f"IDENTITY-{source['accession_number']}",
            "priority": _priority(source),
            "event_id": source["event_id"],
            "cik": source["cik"],
            "accession_number": source["accession_number"],
            "filing_date": source["filing_date"],
            "matched_items": source["matched_items"],
            "prior_identity_status": source["identity_status"],
            "primary_document_url": url,
            "collection_status": "PENDING",
            "source_sha256": "",
            "extracted_symbols": "",
            "adjudication_status": "PENDING",
        })
    priority_order = {"P0_AMBIGUOUS": 0, "P1_TEN_YEAR_WINDOW": 1, "P2_LONG_HISTORY": 2}
    rows.sort(key=lambda row: (priority_order[row["priority"]], row["filing_date"], row["queue_id"]))
    priority_counts = Counter(row["priority"] for row in rows)
    return rows, {
        "report_version": VERSION,
        "status": "IDENTITY_EXTENSION_QUEUE_READY_NO_PRICE_OUTCOMES",
        "protocol_sha256": _sha256(PROTOCOL_PATH),
        "queue_events": len(rows),
        "queue_issuers": len({row["cik"] for row in rows}),
        "priority_counts": dict(sorted(priority_counts.items())),
        "first_filing_date": min(row["filing_date"] for row in rows),
        "last_filing_date": max(row["filing_date"] for row in rows),
        "price_outcomes_opened": False,
        "direction_hypothesis_allowed": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
        "next_stage": protocol["next_stage"],
    }


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run() -> dict[str, Any]:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    rows, report = build(protocol)
    queue_path = _rooted(protocol["output"]["queue"])
    report_path = _rooted(protocol["output"]["report"])
    _write_csv(queue_path, rows)
    report["queue_path"] = protocol["output"]["queue"]
    report["queue_sha256"] = _sha256(queue_path)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
