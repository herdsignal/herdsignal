"""Create and validate the human source-review ledger for SEC ticker candidates."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from herd.sec_targeted_cover_corpus_v2 import extract_tagged_trading_symbols
from herd.sec_trading_symbol_evidence import extract_trading_symbols


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json")
VERSION = "SEC_8K_IDENTITY_SOURCE_REVIEW_V1"
FIELDNAMES = [
    "review_id",
    "accession_number",
    "cik",
    "filing_date",
    "matched_items",
    "extraction_method",
    "candidate_symbols",
    "source_url",
    "source_sha256",
    "decision",
    "approved_symbol",
    "review_note",
]
ALLOWED_DECISIONS = {"PENDING", "VALID", "INVALID", "AMBIGUOUS"}


class Sec8KIdentitySourceReviewError(ValueError):
    """Raised when source review inputs or labels fail closed validation."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise Sec8KIdentitySourceReviewError(f"path escapes repository: {relative}")
    return path


def _locked_paths(protocol: dict[str, Any]) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for specification in protocol["locked_inputs"]:
        path = _rooted(specification["path"])
        if not path.is_file() or _sha256(path) != specification["sha256"]:
            raise Sec8KIdentitySourceReviewError(f"locked input changed: {specification['path']}")
        paths[specification["role"]] = path
    return paths


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_review_rows(protocol: dict[str, Any]) -> list[dict[str, str]]:
    paths = _locked_paths(protocol)
    collection = json.loads(paths["COLLECTION_REPORT"].read_text(encoding="utf-8"))
    if (
        collection.get("candidate_symbol_rows") != protocol["review_scope"]["candidate_rows"]
        or collection.get("candidate_symbols_promoted") != 0
        or collection.get("price_outcomes_opened") is not False
    ):
        raise Sec8KIdentitySourceReviewError("collection report is not review-ready")
    snapshot = paths["LOCAL_SNAPSHOT_MANIFEST"].parent
    rows: list[dict[str, str]] = []
    for source in _read_csv(paths["COLLECTION_INDEX"]):
        if source["extraction_status"] != "CANDIDATE_FOUND":
            continue
        raw = snapshot / "raw" / f"{source['accession_number']}.html"
        if not raw.is_file() or _sha256(raw) != source["source_sha256"]:
            raise Sec8KIdentitySourceReviewError(f"source bytes changed: {source['accession_number']}")
        content = raw.read_bytes()
        tagged = extract_tagged_trading_symbols(content)
        broad = extract_trading_symbols(content)
        if "|".join(broad) != source["extracted_symbols"]:
            raise Sec8KIdentitySourceReviewError(
                f"candidate extraction changed: {source['accession_number']}"
            )
        rows.append({
            "review_id": f"REVIEW-{source['accession_number']}",
            "accession_number": source["accession_number"],
            "cik": source["cik"],
            "filing_date": source["filing_date"],
            "matched_items": source["matched_items"],
            "extraction_method": "XBRL_TAG" if tagged else "VISIBLE_LABEL_REGEX",
            "candidate_symbols": source["extracted_symbols"],
            "source_url": source["primary_document_url"],
            "source_sha256": source["source_sha256"],
            "decision": "PENDING",
            "approved_symbol": "",
            "review_note": "",
        })
    if len(rows) != protocol["review_scope"]["candidate_rows"]:
        raise Sec8KIdentitySourceReviewError("review candidate count changed")
    return sorted(rows, key=lambda row: (row["filing_date"], row["review_id"]))


def _validate_labels(
    expected: list[dict[str, str]], labels: list[dict[str, str]]
) -> None:
    if len(labels) != len(expected) or len({row["review_id"] for row in labels}) != len(labels):
        raise Sec8KIdentitySourceReviewError("review label row count changed")
    immutable = [field for field in FIELDNAMES if field not in {"decision", "approved_symbol", "review_note"}]
    expected_by_id = {row["review_id"]: row for row in expected}
    for row in labels:
        source = expected_by_id.get(row["review_id"])
        if source is None or any(row[field] != source[field] for field in immutable):
            raise Sec8KIdentitySourceReviewError(f"review source fields changed: {row['review_id']}")
        if row["decision"] not in ALLOWED_DECISIONS:
            raise Sec8KIdentitySourceReviewError(f"invalid review decision: {row['review_id']}")
        candidates = set(row["candidate_symbols"].split("|"))
        if row["decision"] == "VALID" and row["approved_symbol"] not in candidates:
            raise Sec8KIdentitySourceReviewError(f"approved symbol is not a candidate: {row['review_id']}")
        if row["decision"] != "VALID" and row["approved_symbol"]:
            raise Sec8KIdentitySourceReviewError(f"non-valid row approved a symbol: {row['review_id']}")


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
        protocol.get("protocol_version") != VERSION
        or protocol.get("status") != "LOCKED_BEFORE_HUMAN_SOURCE_DECISIONS"
        or protocol.get("authority")
        != {
            "price_outcomes_opened": False,
            "identity_promotion_allowed": False,
            "direction_hypothesis_allowed": False,
            "blind_holdout_access": False,
            "operational_action_ratio": 0.0,
        }
    ):
        raise Sec8KIdentitySourceReviewError("source review protocol is not fail-closed")
    expected = build_review_rows(protocol)
    _validate_labels(expected, labels)
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
    return {
        "report_version": VERSION,
        "status": (
            "PENDING_SOURCE_DECISIONS"
            if pending
            else "SOURCE_PRECISION_GATE_PASSED"
            if passed
            else "SOURCE_PRECISION_GATE_FAILED"
        ),
        "protocol_sha256": _sha256(PROTOCOL_PATH),
        "candidate_rows": len(labels),
        "decision_counts": dict(sorted(counts.items())),
        "reviewed_rows": reviewed,
        "wilson_95_lower_bound": wilson,
        "ambiguous_ratio": ambiguous_ratio,
        "checks": checks,
        "source_precision_passed": passed,
        "approved_identity_rows": counts["VALID"] if passed else 0,
        "identity_promotion_allowed": passed,
        "price_outcomes_opened": False,
        "direction_hypothesis_allowed": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
        "next_stage": protocol[
            "next_stage_if_passed" if passed else "next_stage_if_pending"
        ],
    }


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run() -> dict[str, Any]:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    label_path = _rooted(protocol["output"]["labels"])
    if label_path.exists():
        labels = _read_csv(label_path)
    else:
        labels = build_review_rows(protocol)
        _write_csv(label_path, labels)
    report = evaluate(protocol, labels)
    report_path = _rooted(protocol["output"]["report"])
    report["labels_path"] = protocol["output"]["labels"]
    report["labels_sha256"] = _sha256(label_path)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
