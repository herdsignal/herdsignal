"""구조적 SEC 표지 파서의 독립 평가 모집단을 결과 확인 전에 고정한다."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


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
    "collection_status",
]


class Sec8KStructuralEvaluationExpansionError(ValueError):
    """모집단 독립성이나 fail-closed 권한이 바뀌면 발생한다."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise Sec8KStructuralEvaluationExpansionError(
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
            raise Sec8KStructuralEvaluationExpansionError(
                f"locked input changed: {item['path']}"
            )
        paths[item["role"]] = path
    return paths


def build(protocol_path: Path = PROTOCOL) -> tuple[list[dict[str, str]], dict[str, Any]]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    expected_authority = {
        "identity_promotion_allowed": False,
        "price_outcomes_opened": False,
        "direction_hypothesis_allowed": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
    }
    if (
        protocol.get("status")
        != "LOCKED_BEFORE_INDEPENDENT_PRIMARY_DOCUMENT_COLLECTION"
        or protocol.get("authority") != expected_authority
        or protocol["independence"]
        != {
            "development_accession_overlap_allowed": False,
            "prior_unseen_review_overlap_allowed": False,
            "selection_uses_price_or_return_outcomes": False,
            "known_identity_used_as_parser_label": False,
            "canonical_symbol_exposed_to_extractor": False,
        }
    ):
        raise Sec8KStructuralEvaluationExpansionError(
            "evaluation expansion is not fail-closed"
        )
    paths = _locked_paths(protocol)
    corpus_report = json.loads(paths["CORPUS_REPORT"].read_text(encoding="utf-8"))
    prior_review = json.loads(
        paths["PRIOR_UNSEEN_REVIEW_REPORT"].read_text(encoding="utf-8")
    )
    if corpus_report.get("price_outcomes_opened") is not False:
        raise Sec8KStructuralEvaluationExpansionError("corpus exposes price outcomes")
    if (
        prior_review.get("status")
        != "UNSEEN_REVIEW_COMPLETE_INSUFFICIENT_FOR_PRECISION_GATE"
        or prior_review.get("identity_promotion_allowed") is not False
    ):
        raise Sec8KStructuralEvaluationExpansionError(
            "prior unseen review does not require expansion"
        )
    development = {
        row["accession_number"]
        for row in _read_csv(paths["DEVELOPMENT_COLLECTION_INDEX"])
    }
    prior_labels = _read_csv(_rooted(prior_review["labels_path"]))
    prior_unseen = {row["accession_number"] for row in prior_labels}
    selection = protocol["selection"]
    eligible = []
    for source in _read_csv(paths["CORPUS_LEDGER"]):
        if (
            source["form"] not in selection["forms"]
            or source["filing_date"] < selection["minimum_filing_date"]
            or source["identity_status"] != selection["required_identity_status"]
        ):
            continue
        accession = source["accession_number"]
        if accession in development or accession in prior_unseen:
            raise Sec8KStructuralEvaluationExpansionError(
                f"evaluation accession overlaps prior data: {accession}"
            )
        if urlparse(source["primary_document_url"]).hostname != protocol["collection"]["allowed_host"]:
            raise Sec8KStructuralEvaluationExpansionError(
                f"non-SEC source URL: {source['primary_document_url']}"
            )
        eligible.append({
            "evaluation_id": f"STRUCTURAL-EVAL-{accession}",
            "event_id": source["event_id"],
            "accession_number": accession,
            "cik": source["cik"],
            "filing_date": source["filing_date"],
            "matched_items": source["matched_items"],
            "primary_document_url": source["primary_document_url"],
            "collection_status": "PENDING",
        })
    rows = sorted(eligible, key=lambda row: (row["filing_date"], row["evaluation_id"]))
    if (
        len(rows) != selection["expected_documents"]
        or len({row["cik"] for row in rows}) != selection["expected_issuers"]
        or len(rows) < selection["minimum_expected_documents"]
        or len({row["accession_number"] for row in rows}) != len(rows)
    ):
        raise Sec8KStructuralEvaluationExpansionError(
            "evaluation population count changed"
        )
    item_counts = Counter(row["matched_items"] for row in rows)
    return rows, {
        "report_version": protocol["protocol_version"],
        "status": "INDEPENDENT_STRUCTURAL_EVALUATION_QUEUE_READY",
        "documents": len(rows),
        "issuers": len({row["cik"] for row in rows}),
        "first_filing_date": rows[0]["filing_date"],
        "last_filing_date": rows[-1]["filing_date"],
        "matched_item_counts": dict(sorted(item_counts.items())),
        "development_accession_overlap": 0,
        "prior_unseen_review_overlap": 0,
        "canonical_symbols_exposed": 0,
        "selection_uses_price_or_return_outcomes": False,
        "identity_promotion_allowed": False,
        "price_outcomes_opened": False,
        "direction_hypothesis_allowed": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
        "next_stage": protocol["next_stage"],
    }


def run() -> dict[str, Any]:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    rows, report = build()
    queue_path = _rooted(protocol["outputs"]["queue"])
    with queue_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    report["queue_path"] = protocol["outputs"]["queue"]
    report["queue_sha256"] = _sha256(queue_path)
    report_path = _rooted(protocol["outputs"]["report"])
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
