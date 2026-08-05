"""구조적 표지 파서가 새로 찾은 SEC 후보만 독립 원문 검수한다."""

from __future__ import annotations

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
    "candidate_symbols",
    "source_sha256",
    "decision",
    "approved_symbol",
    "review_note",
]


class Sec8KStructuralCandidateReviewError(ValueError):
    """새 표본 경계나 원문 필드가 바뀌면 발생한다."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise Sec8KStructuralCandidateReviewError(f"path escapes repository: {relative}")
    return path


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _locked_paths(protocol: dict[str, Any]) -> dict[str, Path]:
    paths = {}
    for item in protocol["locked_inputs"]:
        path = _rooted(item["path"])
        if not path.is_file() or _sha256(path) != item["sha256"]:
            raise Sec8KStructuralCandidateReviewError(f"locked input changed: {item['path']}")
        paths[item["role"]] = path
    return paths


def expected_rows(protocol: dict[str, Any]) -> list[dict[str, str]]:
    paths = _locked_paths(protocol)
    extractor = json.loads(paths["EXTRACTOR_REPORT"].read_text(encoding="utf-8"))
    if (
        extractor.get("status") != "V2_DEVELOPMENT_COMPLETE_UNSEEN_REVIEW_REQUIRED"
        or extractor.get("independent_precision_claim_allowed") is not False
        or extractor.get("identity_promotion_allowed") is not False
    ):
        raise Sec8KStructuralCandidateReviewError("extractor output is not review-only")
    rows = []
    for source in _read_csv(paths["EXTRACTOR_CANDIDATES"]):
        if source["review_role"] != protocol["review_scope"]["source_role"]:
            continue
        if not source["candidate_symbols"]:
            continue
        rows.append({
            "review_id": f"STRUCTURAL-{source['accession_number']}",
            "accession_number": source["accession_number"],
            "cik": source["cik"],
            "filing_date": source["filing_date"],
            "candidate_symbols": source["candidate_symbols"],
            "source_sha256": source["source_sha256"],
            "decision": "PENDING",
            "approved_symbol": "",
            "review_note": "",
        })
    if len(rows) != protocol["review_scope"]["expected_rows"]:
        raise Sec8KStructuralCandidateReviewError("unseen candidate count changed")
    return rows


def _wilson_lower(successes: int, total: int, z: float = 1.959963984540054) -> float | None:
    if total == 0:
        return None
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = proportion + z * z / (2 * total)
    margin = z * math.sqrt((proportion * (1 - proportion) + z * z / (4 * total)) / total)
    return (centre - margin) / denominator


def evaluate(protocol: dict[str, Any], labels: list[dict[str, str]]) -> dict[str, Any]:
    if (
        protocol.get("status") != "LOCKED_BEFORE_UNSEEN_SOURCE_REVIEW"
        or protocol.get("authority", {}).get("operational_action_ratio") != 0.0
        or protocol["precision_boundary"]["pool_with_development_rows"] is not False
    ):
        raise Sec8KStructuralCandidateReviewError("review protocol is not fail-closed")
    expected = expected_rows(protocol)
    if len(labels) != len(expected):
        raise Sec8KStructuralCandidateReviewError("review row count changed")
    immutable = [field for field in FIELDS if field not in {"decision", "approved_symbol", "review_note"}]
    expected_by_id = {row["review_id"]: row for row in expected}
    allowed = set(protocol["review_scope"]["allowed_decisions"])
    for row in labels:
        source = expected_by_id.get(row["review_id"])
        if source is None or any(row[field] != source[field] for field in immutable):
            raise Sec8KStructuralCandidateReviewError(f"source fields changed: {row['review_id']}")
        if row["decision"] not in allowed:
            raise Sec8KStructuralCandidateReviewError(f"invalid decision: {row['review_id']}")
        candidates = set(row["candidate_symbols"].split("|"))
        if row["decision"] == "VALID" and row["approved_symbol"] not in candidates:
            raise Sec8KStructuralCandidateReviewError(f"approved symbol is not a candidate: {row['review_id']}")
        if row["decision"] != "VALID" and row["approved_symbol"]:
            raise Sec8KStructuralCandidateReviewError(f"non-valid row approved a symbol: {row['review_id']}")
    counts = Counter(row["decision"] for row in labels)
    reviewed = len(labels) - counts["PENDING"]
    wilson = _wilson_lower(counts["VALID"], reviewed)
    boundary = protocol["precision_boundary"]
    enough = reviewed >= boundary["minimum_independent_reviewed_rows"]
    precision = wilson is not None and wilson >= boundary["minimum_wilson_95_lower_bound"]
    pending = counts["PENDING"] > 0
    return {
        "report_version": protocol["protocol_version"],
        "status": "PENDING_UNSEEN_SOURCE_REVIEW" if pending else "UNSEEN_REVIEW_COMPLETE_INSUFFICIENT_FOR_PRECISION_GATE" if not enough else "UNSEEN_PRECISION_GATE_PASSED" if precision else "UNSEEN_PRECISION_GATE_FAILED",
        "rows": len(labels),
        "reviewed_rows": reviewed,
        "decision_counts": dict(sorted(counts.items())),
        "wilson_95_lower_bound": wilson,
        "minimum_independent_reviewed_rows_met": enough,
        "minimum_precision_met": precision,
        "development_rows_pooled": 0,
        "identity_promotion_allowed": enough and precision and not pending,
        "price_outcomes_opened": False,
        "direction_hypothesis_allowed": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
        "next_stage": protocol["next_stage_if_pending"] if pending else protocol["next_stage_if_insufficient"] if not enough else "SEC_8K_TIME_VALID_IDENTITY_PROMOTION_V2" if precision else "STOP_SEC_8K_IDENTITY_PROMOTION_SOURCE_PRECISION_FAILED",
    }


def run() -> dict[str, Any]:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    labels_path = _rooted(protocol["outputs"]["labels"])
    labels = _read_csv(labels_path) if labels_path.exists() else expected_rows(protocol)
    if not labels_path.exists():
        with labels_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(labels)
    report = evaluate(protocol, labels)
    report["labels_path"] = protocol["outputs"]["labels"]
    report["labels_sha256"] = _sha256(labels_path)
    report_path = _rooted(protocol["outputs"]["report"])
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
