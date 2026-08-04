"""SEC 8-K 원문 검수 원장을 재개 가능한 고정 배치로 나눈다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from herd.sec_8k_identity_source_review_v1 import evaluate


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_suffix(".json")


class Sec8KReviewBatchingError(ValueError):
    """Raised when source labels or batching authority fail closed checks."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise Sec8KReviewBatchingError(f"path escapes repository: {relative}")
    return path


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_plan(
    protocol: dict[str, Any],
    source_protocol: dict[str, Any],
    labels: list[dict[str, str]],
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    if protocol.get("status") != "LOCKED_BEFORE_BATCHING":
        raise Sec8KReviewBatchingError("batching protocol is not locked")
    if protocol["authority"]["operational_action_ratio"] != 0.0:
        raise Sec8KReviewBatchingError("batching cannot authorize an action")
    source_report = evaluate(source_protocol, labels)
    config = protocol["batching"]
    ordered = sorted(labels, key=lambda row: (row["filing_date"], row["review_id"]))
    if len(ordered) != config["expected_rows"]:
        raise Sec8KReviewBatchingError("source review row count changed")

    batch_size = config["batch_size"]
    plan: list[dict[str, str]] = []
    for index, row in enumerate(ordered):
        batch_number = index // batch_size + 1
        plan.append({
            "batch_id": f"B{batch_number:03d}",
            "batch_order": str(index % batch_size + 1),
            "review_id": row["review_id"],
            "accession_number": row["accession_number"],
            "cik": row["cik"],
            "filing_date": row["filing_date"],
            "matched_items": row["matched_items"],
            "extraction_method": row["extraction_method"],
            "candidate_symbols": row["candidate_symbols"],
            "source_url": row["source_url"],
            "source_sha256": row["source_sha256"],
            "decision": row["decision"],
            "approved_symbol": row["approved_symbol"],
            "review_note": row["review_note"],
        })
    batch_ids = list(dict.fromkeys(row["batch_id"] for row in plan))
    if len(batch_ids) != config["expected_batches"]:
        raise Sec8KReviewBatchingError("batch count changed")

    batches = []
    for batch_id in batch_ids:
        rows = [row for row in plan if row["batch_id"] == batch_id]
        counts = Counter(row["decision"] for row in rows)
        batches.append({
            "batch_id": batch_id,
            "rows": len(rows),
            "pending": counts["PENDING"],
            "reviewed": len(rows) - counts["PENDING"],
            "complete": counts["PENDING"] == 0,
            "first_review_id": rows[0]["review_id"],
            "last_review_id": rows[-1]["review_id"],
        })
    next_batch = next((row["batch_id"] for row in batches if not row["complete"]), None)
    return plan, {
        "report_version": "SEC_8K_MATERIAL_EVENT_REVIEW_BATCHING_V1",
        "status": "HUMAN_REVIEW_PENDING" if next_batch else "ALL_BATCHES_REVIEWED",
        "protocol_sha256": _sha256(PROTOCOL),
        "source_review_status": source_report["status"],
        "source_labels_sha256": None,
        "rows": len(plan),
        "batch_size": batch_size,
        "batch_count": len(batches),
        "batches": batches,
        "next_pending_batch": next_batch,
        "canonical_editable_ledger": protocol["source_review_labels"],
        "plan_is_read_only_projection": True,
        "auto_labels_created": 0,
        "identity_promotion_allowed": source_report["identity_promotion_allowed"],
        "direction_hypothesis_allowed": False,
        "operational_action_ratio": 0.0,
    }


def build_worklist(
    plan: list[dict[str, str]], batch_id: str
) -> dict[str, Any]:
    rows = [row for row in plan if row["batch_id"] == batch_id]
    if not rows:
        raise Sec8KReviewBatchingError(f"unknown batch: {batch_id}")
    return {
        "batch_id": batch_id,
        "rows": len(rows),
        "pending": sum(row["decision"] == "PENDING" for row in rows),
        "read_only": True,
        "items": [
            {
                "order": int(row["batch_order"]),
                "review_id": row["review_id"],
                "cik": row["cik"],
                "filing_date": row["filing_date"],
                "candidate_symbols": row["candidate_symbols"],
                "source_url": row["source_url"],
                "source_sha256": row["source_sha256"],
                "decision": row["decision"],
            }
            for row in rows
        ],
    }


def run(protocol_path: Path = PROTOCOL) -> dict[str, Any]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    source_protocol_path = _rooted(protocol["source_review_protocol"]["path"])
    if (
        not source_protocol_path.is_file()
        or _sha256(source_protocol_path) != protocol["source_review_protocol"]["sha256"]
    ):
        raise Sec8KReviewBatchingError("source review protocol changed")
    source_protocol = json.loads(source_protocol_path.read_text(encoding="utf-8"))
    label_path = _rooted(protocol["source_review_labels"])
    labels = _read_csv(label_path)
    plan, report = build_plan(protocol, source_protocol, labels)
    report["source_labels_sha256"] = _sha256(label_path)

    plan_path = _rooted(protocol["outputs"]["plan"])
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    with plan_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(plan[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(plan)
    report["plan_path"] = protocol["outputs"]["plan"]
    report["plan_sha256"] = _sha256(plan_path)
    report_path = _rooted(protocol["outputs"]["report"])
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--batch", help="Print a single batch summary after refresh")
    selection.add_argument(
        "--next",
        action="store_true",
        help="Print the next pending batch's read-only source worklist",
    )
    args = parser.parse_args()
    report = run()
    if args.next:
        batch_id = report["next_pending_batch"]
        if batch_id is None:
            print(json.dumps({"status": "ALL_BATCHES_REVIEWED"}, ensure_ascii=False))
            return
        plan = _read_csv(_rooted(report["plan_path"]))
        print(json.dumps(build_worklist(plan, batch_id), ensure_ascii=False, indent=2))
    elif args.batch:
        selected = next(
            (row for row in report["batches"] if row["batch_id"] == args.batch), None
        )
        if selected is None:
            raise Sec8KReviewBatchingError(f"unknown batch: {args.batch}")
        print(json.dumps(selected, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
