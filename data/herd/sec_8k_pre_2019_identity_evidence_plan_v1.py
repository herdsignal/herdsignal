"""2019년 이전 SEC 사건을 issuer 단위 식별 증거 수집 작업으로 묶는다."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_suffix(".json")


class Sec8KPre2019IdentityEvidencePlanV1Error(ValueError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _path(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise Sec8KPre2019IdentityEvidencePlanV1Error("path escapes repository")
    return path


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build(protocol_path: Path = PROTOCOL) -> tuple[list[dict[str, str]], dict[str, Any]]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    authority = protocol.get("authority", {})
    if (
        protocol.get("status") != "LOCKED_ISSUER_LEVEL_EVIDENCE_COLLECTION_PLAN"
        or authority.get("anchor_is_lookup_hint_only") is not True
        or authority.get("automatic_identity_promotion") is not False
        or authority.get("operational_action_ratio") != 0.0
    ):
        raise Sec8KPre2019IdentityEvidencePlanV1Error("plan is not fail-closed")
    paths = {}
    for item in protocol["locked_inputs"]:
        path = _path(item["path"])
        if not path.is_file() or _sha(path) != item["sha256"]:
            raise Sec8KPre2019IdentityEvidencePlanV1Error(f"locked input changed: {item['path']}")
        paths[item["role"]] = path
    report = json.loads(paths["V3_CORPUS_REPORT"].read_text(encoding="utf-8"))
    if report.get("status") != "MODERN_EXCEPTION_COVERAGE_UPDATED" or report.get("unmapped_events") != 646:
        raise Sec8KPre2019IdentityEvidencePlanV1Error("V3 corpus is not ready")

    corpus = _csv(paths["V3_CORPUS"])
    anchors: dict[str, list[dict[str, str]]] = defaultdict(list)
    events: dict[str, list[dict[str, str]]] = defaultdict(list)
    cutoff = protocol["population"]["filing_date_before"]
    for row in corpus:
        if row["identity_status"] != "UNMAPPED":
            anchors[row["cik"]].append(row)
        elif row["filing_date"] < cutoff:
            events[row["cik"]].append(row)
        else:
            raise Sec8KPre2019IdentityEvidencePlanV1Error("unexpected modern unmapped event")

    work = []
    for cik, issuer_events in events.items():
        issuer_events.sort(key=lambda row: (row["filing_date"], row["accession_number"]))
        issuer_anchors = sorted(anchors[cik], key=lambda row: (row["filing_date"], row["accession_number"]))
        route = "REVIEWED_ANCHOR_BOUNDARY" if issuer_anchors else "HISTORICAL_MASTER_DISCOVERY"
        work.append({
            "cik": cik,
            "route": route,
            "event_count": str(len(issuer_events)),
            "first_event_date": issuer_events[0]["filing_date"],
            "last_event_date": issuer_events[-1]["filing_date"],
            "first_accession_number": issuer_events[0]["accession_number"],
            "reviewed_anchor_count": str(len(issuer_anchors)),
            "anchor_symbols": "|".join(sorted({row["canonical_symbol_at_filing"] for row in issuer_anchors})),
            "first_anchor_date": issuer_anchors[0]["filing_date"] if issuer_anchors else "",
            "last_anchor_date": issuer_anchors[-1]["filing_date"] if issuer_anchors else "",
            "required_evidence": "CORPORATE_ACTION_BOUNDARY_THROUGH_EVENT_RANGE" if issuer_anchors else "HISTORICAL_LISTING_IDENTITY_AND_BOUNDARIES",
            "collection_status": "PENDING",
            "review_status": "NOT_REVIEWED",
            "promotion_status": "BLOCKED",
        })
    route_order = {"REVIEWED_ANCHOR_BOUNDARY": 0, "HISTORICAL_MASTER_DISCOVERY": 1}
    work.sort(key=lambda row: (route_order[row["route"]], row["first_event_date"], row["cik"]))
    batch_size = protocol["batching"]["issuer_batch_size"]
    for index, row in enumerate(work):
        row["queue_id"] = f"PRE2019-{index + 1:04d}"
        row["batch_id"] = f"B{index // batch_size + 1:03d}"
    fields = ["queue_id", "batch_id", "cik", "route", "event_count", "first_event_date", "last_event_date", "first_accession_number", "reviewed_anchor_count", "anchor_symbols", "first_anchor_date", "last_anchor_date", "required_evidence", "collection_status", "review_status", "promotion_status"]
    work = [{field: row[field] for field in fields} for row in work]

    population = protocol["population"]
    with_anchor = sum(row["route"] == "REVIEWED_ANCHOR_BOUNDARY" for row in work)
    event_count = sum(int(row["event_count"]) for row in work)
    batch_count = len({row["batch_id"] for row in work})
    if (event_count, len(work), with_anchor, len(work) - with_anchor, batch_count) != (
        population["events"], population["issuers"], population["issuers_with_reviewed_anchor"],
        population["issuers_without_reviewed_anchor"], protocol["batching"]["expected_batches"],
    ):
        raise Sec8KPre2019IdentityEvidencePlanV1Error("queue population changed")
    return work, {
        "report_version": protocol["protocol_version"], "status": "PRE_2019_IDENTITY_EVIDENCE_QUEUE_READY",
        "events": event_count, "issuers": len(work), "issuers_with_reviewed_anchor": with_anchor,
        "issuers_without_reviewed_anchor": len(work) - with_anchor, "batch_size": batch_size,
        "batch_count": batch_count, "pending_issuers": len(work), "reviewed_issuers": 0,
        "promoted_events": 0, "automatic_identity_promotion": False, "price_outcomes_opened": False,
        "direction_hypothesis_allowed": False, "blind_holdout_access": False, "operational_action_ratio": 0.0,
        "next_stage": "COLLECT_PRE_2019_IDENTITY_EVIDENCE_BATCH_B001",
    }


def run() -> dict[str, Any]:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8")); rows, report = build()
    queue = _path(protocol["outputs"]["queue"])
    with queue.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n"); writer.writeheader(); writer.writerows(rows)
    report.update({"queue_path": protocol["outputs"]["queue"], "queue_sha256": _sha(queue)})
    _path(protocol["outputs"]["report"]).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
