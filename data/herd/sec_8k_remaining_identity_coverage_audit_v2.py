"""남은 SEC 8-K 식별 공백을 filing 당시 증거 경로별로 분류한다."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_suffix(".json")


class Sec8KRemainingIdentityCoverageAuditV2Error(ValueError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rooted(relative_path: str) -> Path:
    path = (ROOT / relative_path).resolve()
    if not path.is_relative_to(ROOT):
        raise Sec8KRemainingIdentityCoverageAuditV2Error("path escapes repository")
    return path


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build(protocol_path: Path = PROTOCOL) -> tuple[list[dict[str, str]], dict[str, Any]]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    authority = protocol.get("authority", {})
    if (
        protocol.get("status") != "LOCKED_RESULT_BLIND_IDENTITY_GAP_AUDIT"
        or authority.get("current_ticker_backfill_allowed") is not False
        or authority.get("same_cik_anchor_implies_interval") is not False
        or authority.get("operational_action_ratio") != 0.0
    ):
        raise Sec8KRemainingIdentityCoverageAuditV2Error("audit is not fail-closed")

    inputs: dict[str, Path] = {}
    for locked in protocol["locked_inputs"]:
        path = _rooted(locked["path"])
        if not path.is_file() or _sha(path) != locked["sha256"]:
            raise Sec8KRemainingIdentityCoverageAuditV2Error(
                f"locked input changed: {locked['path']}"
            )
        inputs[locked["role"]] = path

    corpus_report = json.loads(inputs["V2_CORPUS_REPORT"].read_text(encoding="utf-8"))
    if corpus_report.get("status") != "HARD_ADVERSE_CORPUS_V2_IDENTITY_COVERAGE_UPDATED":
        raise Sec8KRemainingIdentityCoverageAuditV2Error("V2 corpus is not ready")

    corpus = _read_csv(inputs["V2_CORPUS_LEDGER"])
    anchors: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in corpus:
        if row["identity_status"] not in {"UNMAPPED", "AMBIGUOUS"}:
            anchors[row["cik"]].append(row)

    cutoff = protocol["classification"]["trading_symbol_cover_field_effective_date"]
    output: list[dict[str, str]] = []
    for row in corpus:
        if row["identity_status"] != "UNMAPPED":
            continue
        same_cik_anchors = sorted(anchors[row["cik"]], key=lambda item: item["filing_date"])
        if row["filing_date"] >= cutoff:
            blocker = "MODERN_COVER_NO_STRUCTURAL_CANDIDATE"
            route = protocol["classification"]["modern_without_candidate"]
        elif same_cik_anchors:
            blocker = "FORM_8K_COVER_PREDATES_REQUIRED_TRADING_SYMBOL_FIELD"
            route = protocol["classification"]["legacy_with_same_cik_anchor"]
        else:
            blocker = "FORM_8K_COVER_PREDATES_REQUIRED_TRADING_SYMBOL_FIELD"
            route = protocol["classification"]["legacy_without_same_cik_anchor"]
        output.append(
            {
                "event_id": row["event_id"],
                "cik": row["cik"],
                "accession_number": row["accession_number"],
                "form": row["form"],
                "filing_date": row["filing_date"],
                "matched_items": row["matched_items"],
                "blocker": blocker,
                "evidence_route": route,
                "same_cik_anchor_count": str(len(same_cik_anchors)),
                "earliest_same_cik_anchor_date": same_cik_anchors[0]["filing_date"] if same_cik_anchors else "",
                "latest_same_cik_anchor_date": same_cik_anchors[-1]["filing_date"] if same_cik_anchors else "",
                "filing_index_url": row["filing_index_url"],
                "primary_document_url": row["primary_document_url"],
            }
        )

    route_counts = Counter(row["evidence_route"] for row in output)
    blocker_counts = Counter(row["blocker"] for row in output)
    expected = protocol["expected"]
    actual = {
        "events": len(corpus),
        "mapped_events": sum(row["identity_status"] not in {"UNMAPPED", "AMBIGUOUS"} for row in corpus),
        "unmapped_events": len(output),
        "legacy_events": blocker_counts["FORM_8K_COVER_PREDATES_REQUIRED_TRADING_SYMBOL_FIELD"],
        "legacy_with_same_cik_anchor": route_counts[protocol["classification"]["legacy_with_same_cik_anchor"]],
        "legacy_without_same_cik_anchor": route_counts[protocol["classification"]["legacy_without_same_cik_anchor"]],
        "modern_without_candidate": route_counts[protocol["classification"]["modern_without_candidate"]],
    }
    if actual != expected:
        raise Sec8KRemainingIdentityCoverageAuditV2Error("coverage population changed")

    return output, {
        "report_version": protocol["protocol_version"],
        "status": "REMAINING_IDENTITY_GAPS_ROUTED",
        **actual,
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "evidence_route_counts": dict(sorted(route_counts.items())),
        "trading_symbol_cover_field_effective_date": cutoff,
        "rule_source": protocol["classification"]["rule_source"],
        "current_ticker_backfill_allowed": False,
        "same_cik_anchor_implies_interval": False,
        "price_outcomes_opened": False,
        "direction_hypothesis_allowed": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
        "next_stage": "COLLECT_TIME_VALID_IDENTITY_EVIDENCE_BY_ROUTE_V1",
    }


def run() -> dict[str, Any]:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    rows, report = build()
    ledger_path = _rooted(protocol["outputs"]["ledger"])
    with ledger_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    report["ledger_path"] = protocol["outputs"]["ledger"]
    report["ledger_sha256"] = _sha(ledger_path)
    report_path = _rooted(protocol["outputs"]["report"])
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
