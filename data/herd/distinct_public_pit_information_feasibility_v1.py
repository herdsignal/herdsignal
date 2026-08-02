"""Audit a structured public PIT candidate without opening price outcomes."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json")
REPORT_PATH = ROOT / "data/reports/distinct_public_pit_information_feasibility_v1.json"
VERSION = "DISTINCT_PUBLIC_PIT_INFORMATION_FEASIBILITY_V1"


class DistinctPublicPitFeasibilityError(ValueError):
    """Raised when a locked source or research boundary changes."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise DistinctPublicPitFeasibilityError(f"path escapes repository: {relative}")
    return path


def _validate_locked_inputs(protocol: dict[str, Any]) -> None:
    for specification in protocol["locked_inputs"]:
        path = _rooted(specification["path"])
        if not path.is_file() or _sha256(path) != specification["sha256"]:
            raise DistinctPublicPitFeasibilityError(
                f"locked input changed: {specification['path']}"
            )
    for source in protocol["submission_sources"]:
        manifest = _rooted(source["path"]) / "manifest.json"
        if not manifest.is_file() or _sha256(manifest) != source["manifest_sha256"]:
            raise DistinctPublicPitFeasibilityError(
                f"submission manifest changed: {source['path']}"
            )


def _ledger_ciks(protocol: dict[str, Any]) -> set[str]:
    ledger = next(
        row for row in protocol["locked_inputs"] if row["role"] == "TIME_VALID_CIK_LEDGER"
    )
    with _rooted(ledger["path"]).open(newline="", encoding="utf-8") as handle:
        return {str(row["cik"]).zfill(10) for row in csv.DictReader(handle)}


def _submission_paths(protocol: dict[str, Any]) -> Iterable[Path]:
    seen: set[Path] = set()
    for source in protocol["submission_sources"]:
        raw = _rooted(source["path"]) / "raw"
        for path in sorted(raw.glob("CIK*-submissions*.json")):
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield resolved
        for path in sorted(raw.glob("CIK*-history-*.json")):
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield resolved


def _columns(payload: dict[str, Any]) -> dict[str, list[Any]]:
    return payload.get("filings", {}).get("recent", payload)


def _filing_rows(payload: dict[str, Any]) -> Iterable[dict[str, str]]:
    columns = _columns(payload)
    required = ("accessionNumber", "filingDate", "acceptanceDateTime", "form")
    count = len(columns.get("accessionNumber", []))
    if count == 0:
        return
    if any(len(columns.get(field, [])) != count for field in required):
        raise DistinctPublicPitFeasibilityError("incomplete SEC submissions columns")
    items = columns.get("items", [""] * count)
    if len(items) != count:
        raise DistinctPublicPitFeasibilityError("incomplete SEC item columns")
    for index in range(count):
        yield {
            "accession_number": str(columns["accessionNumber"][index]),
            "filing_date": str(columns["filingDate"][index]),
            "accepted_at": str(columns["acceptanceDateTime"][index]),
            "form": str(columns["form"][index]),
            "items": str(items[index]),
        }


def audit(protocol: dict[str, Any]) -> dict[str, Any]:
    if (
        protocol.get("protocol_version") != VERSION
        or protocol.get("status") != "LOCKED_BEFORE_COVERAGE_AUDIT"
        or protocol.get("candidate", {}).get("economic_role")
        != "CORPORATE_DAMAGE_VETO_RESEARCH_ONLY"
    ):
        raise DistinctPublicPitFeasibilityError("feasibility protocol is not locked")
    authority = protocol.get("authority", {})
    if authority != {
        "price_outcomes_opened": False,
        "direction_hypothesis_allowed": False,
        "herd_formula_change_allowed": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
    }:
        raise DistinctPublicPitFeasibilityError("unsupported research authority granted")

    _validate_locked_inputs(protocol)
    ledger_ciks = _ledger_ciks(protocol)
    eligible_forms = set(protocol["candidate"]["forms"])
    eligible_items = set(protocol["candidate"]["items"])
    start = protocol["audit_period"]["start"]
    end = protocol["audit_period"]["end"]

    submission_ciks: set[str] = set()
    events: dict[str, dict[str, Any]] = {}
    for path in _submission_paths(protocol):
        cik = path.name[3:13]
        if cik not in ledger_ciks:
            continue
        submission_ciks.add(cik)
        payload = json.loads(path.read_text(encoding="utf-8"))
        for filing in _filing_rows(payload):
            if filing["form"] not in eligible_forms:
                continue
            if not start <= filing["filing_date"] <= end:
                continue
            matched = sorted(
                eligible_items
                & {token.strip() for token in filing["items"].split(",") if token.strip()}
            )
            if not matched or not filing["accession_number"]:
                continue
            events.setdefault(
                filing["accession_number"],
                {
                    **filing,
                    "cik": cik,
                    "matched_items": matched,
                },
            )

    rows = sorted(events.values(), key=lambda row: (row["accepted_at"], row["accession_number"]))
    accepted_rows = [row for row in rows if row["accepted_at"]]
    event_dates = [date.fromisoformat(row["filing_date"]) for row in rows]
    event_years = sorted({value.year for value in event_dates})
    item_counts = Counter(item for row in rows for item in row["matched_items"])
    event_issuers = {row["cik"] for row in rows}
    coverage_ratio = len(submission_ciks) / len(ledger_ciks) if ledger_ciks else 0.0
    history_years = (
        (max(event_dates) - min(event_dates)).days / 365.2425
        if len(event_dates) >= 2
        else 0.0
    )
    acceptance_ratio = len(accepted_rows) / len(rows) if rows else 0.0

    gate = protocol["coverage_gate"]
    checks = {
        "submission_cik_coverage": coverage_ratio
        >= gate["minimum_submission_cik_coverage_ratio"],
        "event_history_years": history_years >= gate["minimum_event_history_years"],
        "event_year_count": len(event_years) >= gate["minimum_event_year_count"],
        "event_filings": len(rows) >= gate["minimum_event_filings"],
        "event_issuers": len(event_issuers) >= gate["minimum_event_issuers"],
        "acceptance_timestamp_ratio": acceptance_ratio
        >= gate["required_acceptance_timestamp_ratio"],
    }
    coverage_passed = all(checks.values())
    next_stage = (
        protocol["promotion_if_coverage_passes"]["next_stage"]
        if coverage_passed
        else "BLOCKED_NO_ADMISSIBLE_DISTINCT_PUBLIC_PIT_SOURCE"
    )
    return {
        "report_version": VERSION,
        "status": (
            "COVERAGE_PASS_CORPUS_REQUIRED_NO_DIRECTION_AUTHORITY"
            if coverage_passed
            else "COVERAGE_FAILED_NO_DIRECTION_AUTHORITY"
        ),
        "protocol_sha256": _sha256(PROTOCOL_PATH),
        "candidate": protocol["candidate"]["id"],
        "allowed_role": "CORPORATE_DAMAGE_VETO_RESEARCH_ONLY",
        "ledger_ciks": len(ledger_ciks),
        "submission_ciks": len(submission_ciks),
        "submission_cik_coverage_ratio": coverage_ratio,
        "event_filings": len(rows),
        "event_issuers": len(event_issuers),
        "event_history_years": history_years,
        "first_event_date": min(event_dates).isoformat() if event_dates else None,
        "last_event_date": max(event_dates).isoformat() if event_dates else None,
        "event_year_count": len(event_years),
        "event_years": event_years,
        "acceptance_timestamp_ratio": acceptance_ratio,
        "item_counts": dict(sorted(item_counts.items())),
        "checks": checks,
        "coverage_passed": coverage_passed,
        "price_outcomes_opened": False,
        "direction_hypothesis_allowed": False,
        "herd_formula_change_allowed": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
        "next_stage": next_stage,
    }


def run(report_path: Path = REPORT_PATH) -> dict[str, Any]:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    report = audit(protocol)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
