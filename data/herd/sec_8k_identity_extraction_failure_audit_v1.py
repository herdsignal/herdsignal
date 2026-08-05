"""실패한 SEC ticker 후보를 파서 변경 전에 원인별로 고정한다."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_suffix(".json")
REPORT = ROOT / "data/reports/sec_8k_identity_extraction_failure_audit_v1.json"


class Sec8KIdentityFailureAuditError(ValueError):
    """감사 입력이나 연구 경계가 바뀌면 발생한다."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise Sec8KIdentityFailureAuditError(f"path escapes repository: {relative}")
    return path


def _inputs(protocol: dict[str, Any]) -> dict[str, Path]:
    paths = {}
    for item in protocol["locked_inputs"]:
        path = _rooted(item["path"])
        if not path.is_file() or _sha256(path) != item["sha256"]:
            raise Sec8KIdentityFailureAuditError(f"locked input changed: {item['path']}")
        paths[item["role"]] = path
    return paths


def audit(protocol_path: Path = PROTOCOL) -> dict[str, Any]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if (
        protocol.get("status") != "LOCKED_AFTER_SOURCE_PRECISION_GATE_FAILURE"
        or protocol.get("authority")
        != {
            "identity_promotion_allowed": False,
            "direction_hypothesis_allowed": False,
            "blind_holdout_access": False,
            "operational_action_ratio": 0.0,
        }
    ):
        raise Sec8KIdentityFailureAuditError("failure audit is not fail-closed")
    paths = _inputs(protocol)
    source_report = json.loads(paths["SOURCE_REVIEW_REPORT"].read_text(encoding="utf-8"))
    if (
        source_report.get("status") != "SOURCE_PRECISION_GATE_FAILED"
        or source_report.get("identity_promotion_allowed") is not False
    ):
        raise Sec8KIdentityFailureAuditError("source precision failure is not locked")

    with paths["SOURCE_REVIEW_LABELS"].open(newline="", encoding="utf-8") as handle:
        labels = list(csv.DictReader(handle))
    with paths["COLLECTION_INDEX"].open(newline="", encoding="utf-8") as handle:
        collection = list(csv.DictReader(handle))
    invalid = [row for row in labels if row["decision"] == "INVALID"]
    markup = set(protocol["classification"]["markup_tokens"])
    families = Counter()
    failures = []
    for row in invalid:
        candidates = set(row["candidate_symbols"].split("|"))
        family = (
            protocol["classification"]["markup_error_family"]
            if candidates and candidates <= markup
            else protocol["classification"]["other_error_family"]
        )
        families[family] += 1
        failures.append({
            "review_id": row["review_id"],
            "accession_number": row["accession_number"],
            "extraction_method": row["extraction_method"],
            "candidate_symbols": row["candidate_symbols"].split("|"),
            "error_family": family,
            "review_note": row["review_note"],
        })
    no_candidate = sum(row["extraction_status"] == "NO_CANDIDATE_FOUND" for row in collection)
    boundary = protocol["evaluation_boundary"]
    return {
        "report_version": protocol["protocol_version"],
        "status": "FAILURE_AUDIT_COMPLETE_PARSER_CHANGE_ALLOWED",
        "source_review_status": source_report["status"],
        "reviewed_rows": len(labels),
        "invalid_rows": len(invalid),
        "error_families": dict(sorted(families.items())),
        "all_invalids_are_markup_tokens": len(invalid) > 0
        and families == {protocol["classification"]["markup_error_family"]: len(invalid)},
        "no_candidate_rows": no_candidate,
        "failures": failures,
        "development_boundary": boundary,
        "recommended_parser_change": {
            "id": "STRUCTURAL_COVER_TABLE_CELL_EXTRACTION",
            "reject_html_element_names": sorted(markup),
            "retain_xbrl_trading_symbol_extraction": True,
            "development_regression_rows": len(labels),
            "independent_precision_claim_allowed": False,
        },
        "next_stage": protocol["next_stage"],
        **protocol["authority"],
    }


def run() -> dict[str, Any]:
    report = audit()
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
