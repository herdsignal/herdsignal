"""독립 SEC 구조적 ticker 후보를 단일 원장과 고정 배치로 검수한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_suffix(".json")
FIELDS = [
    "review_id",
    "accession_number",
    "cik",
    "filing_date",
    "matched_items",
    "extraction_method",
    "candidate_symbols",
    "source_sha256",
    "decision",
    "approved_symbol",
    "review_note",
]
BATCH_FIELDS = ["batch_id", "batch_order", *FIELDS]


class Sec8KStructuralEvaluationReviewError(ValueError):
    """독립 검수 입력·라벨·권한 경계가 바뀌면 발생한다."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise Sec8KStructuralEvaluationReviewError(
            f"path escapes repository: {relative}"
        )
    return path


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _locked_paths(protocol: dict[str, Any]) -> dict[str, Path]:
    paths = {}
    for item in protocol["locked_inputs"]:
        path = _rooted(item["path"])
        if not path.is_file() or _sha256(path) != item["sha256"]:
            raise Sec8KStructuralEvaluationReviewError(
                f"locked input changed: {item['path']}"
            )
        paths[item["role"]] = path
    return paths


def expected_rows(protocol: dict[str, Any]) -> list[dict[str, str]]:
    paths = _locked_paths(protocol)
    extraction = json.loads(paths["EXTRACTION_REPORT"].read_text(encoding="utf-8"))
    if (
        extraction.get("status")
        != "INDEPENDENT_EXTRACTION_COMPLETE_SOURCE_REVIEW_REQUIRED"
        or extraction.get("human_labels_created") != 0
        or extraction.get("identity_promotion_allowed") is not False
    ):
        raise Sec8KStructuralEvaluationReviewError(
            "independent extraction is not review-ready"
        )
    rows = []
    for source in _read_csv(paths["EXTRACTION_CANDIDATES"]):
        if not source["candidate_symbols"]:
            continue
        rows.append({
            "review_id": f"INDEPENDENT-{source['accession_number']}",
            "accession_number": source["accession_number"],
            "cik": source["cik"],
            "filing_date": source["filing_date"],
            "matched_items": source["matched_items"],
            "extraction_method": source["extraction_method"],
            "candidate_symbols": source["candidate_symbols"],
            "source_sha256": source["source_sha256"],
            "decision": "PENDING",
            "approved_symbol": "",
            "review_note": "",
        })
    rows.sort(key=lambda row: (row["filing_date"], row["review_id"]))
    if len(rows) != protocol["review_scope"]["expected_candidate_rows"]:
        raise Sec8KStructuralEvaluationReviewError("candidate row count changed")
    return rows


def _validate_labels(
    protocol: dict[str, Any], expected: list[dict[str, str]], labels: list[dict[str, str]]
) -> None:
    if len(labels) != len(expected) or len({row["review_id"] for row in labels}) != len(labels):
        raise Sec8KStructuralEvaluationReviewError("review label row count changed")
    immutable = [field for field in FIELDS if field not in {"decision", "approved_symbol", "review_note"}]
    expected_by_id = {row["review_id"]: row for row in expected}
    allowed = set(protocol["review_scope"]["allowed_decisions"])
    for row in labels:
        source = expected_by_id.get(row["review_id"])
        if source is None or any(row[field] != source[field] for field in immutable):
            raise Sec8KStructuralEvaluationReviewError(
                f"source fields changed: {row['review_id']}"
            )
        if row["decision"] not in allowed:
            raise Sec8KStructuralEvaluationReviewError(
                f"invalid decision: {row['review_id']}"
            )
        candidates = set(row["candidate_symbols"].split("|"))
        if row["decision"] == "VALID" and row["approved_symbol"] not in candidates:
            raise Sec8KStructuralEvaluationReviewError(
                f"approved symbol is not a candidate: {row['review_id']}"
            )
        if row["decision"] != "VALID" and row["approved_symbol"]:
            raise Sec8KStructuralEvaluationReviewError(
                f"non-valid row approved a symbol: {row['review_id']}"
            )


def _wilson_lower(successes: int, total: int, z: float = 1.959963984540054) -> float | None:
    if total == 0:
        return None
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = proportion + z * z / (2 * total)
    margin = z * math.sqrt((proportion * (1 - proportion) + z * z / (4 * total)) / total)
    return (centre - margin) / denominator


def evaluate(protocol: dict[str, Any], labels: list[dict[str, str]]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    expected_authority = {
        "identity_promotion_allowed": False,
        "price_outcomes_opened": False,
        "direction_hypothesis_allowed": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
    }
    if (
        protocol.get("status") != "LOCKED_BEFORE_INDEPENDENT_HUMAN_REVIEW"
        or protocol.get("authority") != expected_authority
        or protocol["review_scope"]["known_identity_labels_allowed"] is not False
    ):
        raise Sec8KStructuralEvaluationReviewError(
            "independent review is not fail-closed"
        )
    expected = expected_rows(protocol)
    _validate_labels(protocol, expected, labels)
    batch_size = protocol["batching"]["batch_size"]
    plan = []
    for index, row in enumerate(labels):
        plan.append({
            "batch_id": f"B{index // batch_size + 1:03d}",
            "batch_order": str(index % batch_size + 1),
            **row,
        })
    batches = []
    for batch_id in dict.fromkeys(row["batch_id"] for row in plan):
        rows = [row for row in plan if row["batch_id"] == batch_id]
        counts = Counter(row["decision"] for row in rows)
        batches.append({
            "batch_id": batch_id,
            "rows": len(rows),
            "reviewed": len(rows) - counts["PENDING"],
            "pending": counts["PENDING"],
            "complete": counts["PENDING"] == 0,
        })
    if (
        len(batches) != protocol["batching"]["expected_batches"]
        or batches[-1]["rows"] != protocol["batching"]["last_batch_rows"]
    ):
        raise Sec8KStructuralEvaluationReviewError("batch shape changed")
    counts = Counter(row["decision"] for row in labels)
    reviewed = len(labels) - counts["PENDING"]
    wilson = _wilson_lower(counts["VALID"], reviewed)
    ambiguous_ratio = counts["AMBIGUOUS"] / reviewed if reviewed else None
    gate = protocol["precision_gate"]
    checks = {
        "minimum_reviewed_rows": reviewed >= gate["minimum_reviewed_rows"],
        "minimum_wilson_95_lower_bound": wilson is not None
        and wilson >= gate["minimum_wilson_95_lower_bound"],
        "maximum_ambiguous_ratio": ambiguous_ratio is not None
        and ambiguous_ratio <= gate["maximum_ambiguous_ratio"],
        "all_rows_adjudicated": counts["PENDING"] == 0,
    }
    passed = all(checks.values())
    pending = counts["PENDING"] > 0
    next_batch = next((batch["batch_id"] for batch in batches if not batch["complete"]), None)
    report = {
        "report_version": protocol["protocol_version"],
        "status": "INDEPENDENT_HUMAN_REVIEW_PENDING" if pending else "INDEPENDENT_SOURCE_PRECISION_GATE_PASSED" if passed else "INDEPENDENT_SOURCE_PRECISION_GATE_FAILED",
        "rows": len(labels),
        "reviewed_rows": reviewed,
        "decision_counts": dict(sorted(counts.items())),
        "wilson_95_lower_bound": wilson,
        "ambiguous_ratio": ambiguous_ratio,
        "checks": checks,
        "batch_size": batch_size,
        "batch_count": len(batches),
        "batches": batches,
        "next_pending_batch": next_batch,
        "known_identity_labels_used": 0,
        "identity_promotion_allowed": passed,
        "price_outcomes_opened": False,
        "direction_hypothesis_allowed": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
        "next_stage": f"COMPLETE_SEC_8K_INDEPENDENT_REVIEW_BATCH_{next_batch}" if pending else protocol["next_stage_if_passed"] if passed else protocol["next_stage_if_failed"],
    }
    return plan, report


def run() -> dict[str, Any]:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    labels_path = _rooted(protocol["outputs"]["labels"])
    labels = _read_csv(labels_path) if labels_path.exists() else expected_rows(protocol)
    if not labels_path.exists():
        _write_csv(labels_path, labels, FIELDS)
    plan, report = evaluate(protocol, labels)
    plan_path = _rooted(protocol["outputs"]["batch_plan"])
    _write_csv(plan_path, plan, BATCH_FIELDS)
    report["labels_path"] = protocol["outputs"]["labels"]
    report["labels_sha256"] = _sha256(labels_path)
    report["batch_plan_path"] = protocol["outputs"]["batch_plan"]
    report["batch_plan_sha256"] = _sha256(plan_path)
    report_path = _rooted(protocol["outputs"]["report"])
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--next", action="store_true")
    args = parser.parse_args()
    report = run()
    if args.next:
        batch_id = report["next_pending_batch"]
        plan = _read_csv(_rooted(report["batch_plan_path"]))
        print(json.dumps({
            "batch_id": batch_id,
            "items": [row for row in plan if row["batch_id"] == batch_id],
        }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
