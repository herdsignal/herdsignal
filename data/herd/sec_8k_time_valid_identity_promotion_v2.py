"""독립 정밀도 통과 뒤 원문 검수된 SEC 사건 식별만 승격한다."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_suffix(".json")
FIELDS = [
    "accession_number", "cik", "filing_date", "approved_symbol",
    "source_sha256", "review_source", "identity_scope",
]


class Sec8KIdentityPromotionV2Error(ValueError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise Sec8KIdentityPromotionV2Error(f"path escapes repository: {relative}")
    return path


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _locked_paths(protocol: dict[str, Any]) -> dict[str, Path]:
    paths = {}
    for item in protocol["locked_inputs"]:
        path = _rooted(item["path"])
        if not path.is_file() or _sha256(path) != item["sha256"]:
            raise Sec8KIdentityPromotionV2Error(f"locked input changed: {item['path']}")
        paths[item["role"]] = path
    return paths


def build(protocol_path: Path = PROTOCOL) -> tuple[list[dict[str, str]], dict[str, Any]]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if (
        protocol.get("status") != "LOCKED_AFTER_INDEPENDENT_PRECISION_GATE_PASS"
        or protocol["promotion"]["infer_open_ended_ticker_interval"] is not False
        or protocol["authority"]["operational_action_ratio"] != 0.0
    ):
        raise Sec8KIdentityPromotionV2Error("promotion protocol is not fail-closed")
    paths = _locked_paths(protocol)
    gate = json.loads(paths["INDEPENDENT_REVIEW_REPORT"].read_text(encoding="utf-8"))
    if (
        gate.get("status") != "INDEPENDENT_SOURCE_PRECISION_GATE_PASSED"
        or gate.get("identity_promotion_allowed") is not True
        or not all(gate.get("checks", {}).values())
    ):
        raise Sec8KIdentityPromotionV2Error("independent precision gate did not pass")
    candidates = {
        row["accession_number"]: row
        for row in _read_csv(paths["V2_CANDIDATES"])
    }
    sources = [
        ("V1_SOURCE_REVIEW", _read_csv(paths["V1_SOURCE_REVIEW"])),
        ("V2_UNSEEN_REVIEW", _read_csv(paths["V2_UNSEEN_REVIEW"])),
        ("V2_CORRECTION_REVIEW", _read_csv(paths["V2_CORRECTION_REVIEW"])),
    ]
    expected = protocol["promotion"]
    expected_counts = {
        "V1_SOURCE_REVIEW": expected["expected_v1_valid_rows"],
        "V2_UNSEEN_REVIEW": expected["expected_v2_unseen_valid_rows"],
        "V2_CORRECTION_REVIEW": expected["expected_v2_correction_valid_rows"],
    }
    rows = []
    counts = Counter()
    for source_name, reviews in sources:
        valid = [row for row in reviews if row["decision"] == "VALID"]
        if len(valid) != expected_counts[source_name]:
            raise Sec8KIdentityPromotionV2Error(f"valid review count changed: {source_name}")
        for review in valid:
            candidate = candidates.get(review["accession_number"])
            if candidate is None:
                raise Sec8KIdentityPromotionV2Error("review accession missing from V2 candidates")
            if (
                review["approved_symbol"] not in candidate["candidate_symbols"].split("|")
                or review["source_sha256"] != candidate["source_sha256"]
                or review["cik"] != candidate["cik"]
                or review["filing_date"] != candidate["filing_date"]
            ):
                raise Sec8KIdentityPromotionV2Error(
                    f"review does not match V2 source: {review['accession_number']}"
                )
            rows.append({
                "accession_number": review["accession_number"],
                "cik": review["cik"],
                "filing_date": review["filing_date"],
                "approved_symbol": review["approved_symbol"],
                "source_sha256": review["source_sha256"],
                "review_source": source_name,
                "identity_scope": "EXACT_FILING_DATE_EVENT_ONLY",
            })
            counts[source_name] += 1
    rows.sort(key=lambda row: (row["filing_date"], row["accession_number"]))
    if len(rows) != expected["expected_promoted_rows"] or len({r["accession_number"] for r in rows}) != len(rows):
        raise Sec8KIdentityPromotionV2Error("promoted identity row count changed")
    report = {
        "report_version": protocol["protocol_version"],
        "status": "TIME_VALID_EVENT_IDENTITY_PROMOTION_COMPLETE",
        "promoted_rows": len(rows),
        "promoted_issuers": len({row["cik"] for row in rows}),
        "review_source_counts": dict(sorted(counts.items())),
        "identity_scope": "EXACT_FILING_DATE_EVENT_ONLY",
        "open_ended_intervals_inferred": 0,
        "price_outcomes_opened": False,
        "direction_hypothesis_allowed": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
        "next_stage": protocol["next_stage"],
    }
    return rows, report


def run() -> dict[str, Any]:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    rows, report = build()
    ledger = _rooted(protocol["outputs"]["ledger"])
    with ledger.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    report["ledger_path"] = protocol["outputs"]["ledger"]
    report["ledger_sha256"] = _sha256(ledger)
    report_path = _rooted(protocol["outputs"]["report"])
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
