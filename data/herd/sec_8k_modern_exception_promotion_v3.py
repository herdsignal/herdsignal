"""현대 SEC 표지 예외 한 건을 명시적 원문 검수로 승격한다."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_suffix(".json")


class Sec8KModernExceptionPromotionV3Error(ValueError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _path(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise Sec8KModernExceptionPromotionV3Error("path escapes repository")
    return path


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build(protocol_path: Path = PROTOCOL) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any], dict[str, Any]]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    authority = protocol.get("authority", {})
    if (
        protocol.get("status") != "LOCKED_SINGLE_MODERN_EXCEPTION_REVIEW"
        or authority.get("parser_changed") is not False
        or authority.get("infer_open_ended_ticker_interval") is not False
        or authority.get("operational_action_ratio") != 0.0
    ):
        raise Sec8KModernExceptionPromotionV3Error("promotion is not fail-closed")
    paths = {}
    for item in protocol["locked_inputs"]:
        path = _path(item["path"])
        if not path.is_file() or _sha(path) != item["sha256"]:
            raise Sec8KModernExceptionPromotionV3Error(f"locked input changed: {item['path']}")
        paths[item["role"]] = path

    gaps = {row["accession_number"]: row for row in _csv(paths["GAP_AUDIT"])}
    sources = {row["accession_number"]: row for row in _csv(paths["SOURCE_COLLECTION"])}
    reviews = _csv(paths["MANUAL_REVIEW"])
    if len(reviews) != protocol["expected"]["review_rows"]:
        raise Sec8KModernExceptionPromotionV3Error("review population changed")
    additions = []
    for review in reviews:
        gap = gaps.get(review["accession_number"])
        source = sources.get(review["accession_number"])
        if (
            review["decision"] != "VALID"
            or review["review_method"] != "SEC_PRIMARY_DOCUMENT_MANUAL_REVIEW"
            or not review["review_note"].strip()
            or not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", review["approved_symbol"])
            or gap is None
            or gap["evidence_route"] != "MODERN_COVER_ALTERNATE_DOCUMENT_REVIEW"
            or source is None
            or source["source_sha256"] != review["source_sha256"]
            or source["cik"] != review["cik"]
            or source["filing_date"] != review["filing_date"]
        ):
            raise Sec8KModernExceptionPromotionV3Error("manual review does not match locked SEC source")
        additions.append({
            "accession_number": review["accession_number"], "cik": review["cik"],
            "filing_date": review["filing_date"], "approved_symbol": review["approved_symbol"],
            "source_sha256": review["source_sha256"], "review_source": "MODERN_COVER_EXCEPTION_REVIEW",
            "identity_scope": "EXACT_FILING_DATE_EVENT_ONLY",
        })

    promotions = _csv(paths["V2_PROMOTIONS"]) + additions
    promotions.sort(key=lambda row: (row["filing_date"], row["accession_number"]))
    if len(promotions) != protocol["expected"]["promotions_after_merge"] or len({r["accession_number"] for r in promotions}) != len(promotions):
        raise Sec8KModernExceptionPromotionV3Error("promotion count changed")

    addition_by_accession = {row["accession_number"]: row for row in additions}
    corpus = _csv(paths["V2_CORPUS"])
    changed = 0
    for row in corpus:
        promotion = addition_by_accession.get(row["accession_number"])
        if promotion is None:
            continue
        if row["identity_status"] != "UNMAPPED" or row["cik"] != promotion["cik"] or row["filing_date"] != promotion["filing_date"]:
            raise Sec8KModernExceptionPromotionV3Error("exception conflicts with V2 corpus")
        row["canonical_symbol_at_filing"] = promotion["approved_symbol"]
        row["identity_status"] = "SEC_PRIMARY_DOCUMENT_REVIEWED"
        changed += 1
    counts = Counter(row["identity_status"] for row in corpus)
    mapped = sum(value for key, value in counts.items() if key not in {"UNMAPPED", "AMBIGUOUS"})
    expected = protocol["expected"]
    if len(corpus) != expected["events"] or changed != 1 or mapped != expected["mapped_after_merge"] or counts["UNMAPPED"] != expected["unmapped_after_merge"]:
        raise Sec8KModernExceptionPromotionV3Error("V3 corpus coverage changed")

    common = {"price_outcomes_opened": False, "direction_hypothesis_allowed": False, "blind_holdout_access": False, "operational_action_ratio": 0.0}
    promotion_report = {"report_version": "SEC_8K_TIME_VALID_IDENTITY_PROMOTION_V3", "status": "MODERN_EXCEPTION_IDENTITY_PROMOTED", "promoted_rows": len(promotions), "newly_promoted_rows": 1, "identity_scope": "EXACT_FILING_DATE_EVENT_ONLY", "open_ended_intervals_inferred": 0, **common}
    corpus_report = {"report_version": "SEC_8K_HARD_ADVERSE_EVENT_CORPUS_V3", "status": "MODERN_EXCEPTION_COVERAGE_UPDATED", "events": len(corpus), "newly_mapped_events": 1, "mapped_events": mapped, "unmapped_events": counts["UNMAPPED"], "ambiguous_events": counts["AMBIGUOUS"], "identity_status_counts": dict(sorted(counts.items())), **common, "next_stage": "COLLECT_PRE_2019_TIME_VALID_IDENTITY_EVIDENCE_V1"}
    return promotions, corpus, promotion_report, corpus_report


def run() -> dict[str, Any]:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    promotions, corpus, promotion_report, corpus_report = build()
    promotion_ledger = _path(protocol["outputs"]["promotion_ledger"]); _write(promotion_ledger, promotions)
    corpus_ledger = _path(protocol["outputs"]["corpus_ledger"]); _write(corpus_ledger, corpus)
    promotion_report.update({"ledger_path": protocol["outputs"]["promotion_ledger"], "ledger_sha256": _sha(promotion_ledger)})
    corpus_report.update({"ledger_path": protocol["outputs"]["corpus_ledger"], "ledger_sha256": _sha(corpus_ledger)})
    _path(protocol["outputs"]["promotion_report"]).write_text(json.dumps(promotion_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _path(protocol["outputs"]["corpus_report"]).write_text(json.dumps(corpus_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return corpus_report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
