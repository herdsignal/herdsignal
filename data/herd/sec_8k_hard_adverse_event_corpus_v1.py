"""Build an immutable metadata ledger for hard-adverse Form 8-K events."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from herd.distinct_public_pit_information_feasibility_v1 import collect_candidate_events


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json")
VERSION = "SEC_8K_HARD_ADVERSE_EVENT_CORPUS_V1"
ACCESSION = re.compile(r"^\d{10}-\d{2}-\d{6}$")
FIELDNAMES = [
    "event_id",
    "cik",
    "canonical_symbol_at_filing",
    "identity_status",
    "accession_number",
    "form",
    "filing_date",
    "accepted_at",
    "matched_items",
    "filing_index_url",
    "primary_document_url",
]


class Sec8KHardAdverseCorpusError(ValueError):
    """Raised when immutable corpus inputs or no-action boundaries drift."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise Sec8KHardAdverseCorpusError(f"path escapes repository: {relative}")
    return path


def _load_locked(protocol: dict[str, Any]) -> dict[str, Any]:
    loaded: dict[str, Any] = {}
    for specification in protocol["locked_inputs"]:
        path = _rooted(specification["path"])
        if not path.is_file() or _sha256(path) != specification["sha256"]:
            raise Sec8KHardAdverseCorpusError(f"locked input changed: {specification['path']}")
        if path.suffix == ".json":
            loaded[specification["role"]] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def _identity_intervals(path: Path) -> dict[str, list[dict[str, str]]]:
    intervals: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            intervals[str(row["cik"]).zfill(10)].append(row)
    return intervals


def _symbols_for_date(
    intervals: dict[str, list[dict[str, str]]], cik: str, filing_date: str
) -> list[str]:
    symbols = set()
    for row in intervals.get(cik, []):
        valid_to = row["valid_to"] or "9999-12-31"
        if row["valid_from"] <= filing_date <= valid_to:
            symbols.add(row["canonical_symbol"])
    return sorted(symbols)


def build(protocol: dict[str, Any]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    if (
        protocol.get("protocol_version") != VERSION
        or protocol.get("status") != "LOCKED_AFTER_SOURCE_COVERAGE_BEFORE_PRICE_OUTCOMES"
        or protocol.get("authority")
        != {
            "price_outcomes_opened": False,
            "direction_hypothesis_allowed": False,
            "herd_formula_change_allowed": False,
            "blind_holdout_access": False,
            "operational_action_ratio": 0.0,
        }
    ):
        raise Sec8KHardAdverseCorpusError("corpus protocol is not fail-closed")
    locked = _load_locked(protocol)
    feasibility = locked["FEASIBILITY_REPORT"]
    if (
        feasibility.get("coverage_passed") is not True
        or feasibility.get("direction_hypothesis_allowed") is not False
        or feasibility.get("price_outcomes_opened") is not False
    ):
        raise Sec8KHardAdverseCorpusError("source feasibility did not pass safely")

    feasibility_protocol = locked["FEASIBILITY_PROTOCOL"]
    _, _, source_rows = collect_candidate_events(feasibility_protocol)
    expected = protocol["expected_source_inventory"]
    source_dates = [date.fromisoformat(row["filing_date"]) for row in source_rows]
    if (
        len(source_rows) != expected["event_filings"]
        or len({row["cik"] for row in source_rows}) != expected["event_issuers"]
        or min(source_dates).isoformat() != expected["first_event_date"]
        or max(source_dates).isoformat() != expected["last_event_date"]
        or sum(bool(row["accepted_at"]) for row in source_rows) / len(source_rows)
        != expected["acceptance_timestamp_ratio"]
    ):
        raise Sec8KHardAdverseCorpusError("source inventory changed after feasibility lock")

    ledger_path = _rooted(next(
        row["path"] for row in protocol["locked_inputs"]
        if row["role"] == "TIME_VALID_CIK_LEDGER"
    ))
    intervals = _identity_intervals(ledger_path)
    rows: list[dict[str, str]] = []
    for source in source_rows:
        symbols = _symbols_for_date(intervals, source["cik"], source["filing_date"])
        identity_status = (
            "TIME_VALID_MAPPED"
            if len(symbols) == 1
            else "AMBIGUOUS"
            if len(symbols) > 1
            else "UNMAPPED"
        )
        accession = source["accession_number"]
        if not ACCESSION.fullmatch(accession):
            raise Sec8KHardAdverseCorpusError(f"invalid accession: {accession}")
        compact = accession.replace("-", "")
        rows.append({
            "event_id": f"SEC8K-{accession}",
            "cik": source["cik"],
            "canonical_symbol_at_filing": symbols[0] if len(symbols) == 1 else "",
            "identity_status": identity_status,
            "accession_number": accession,
            "form": source["form"],
            "filing_date": source["filing_date"],
            "accepted_at": source["accepted_at"],
            "matched_items": "|".join(source["matched_items"]),
            "filing_index_url": (
                f"https://www.sec.gov/Archives/edgar/data/{int(source['cik'])}/"
                f"{compact}/{accession}-index.html"
            ),
            "primary_document_url": (
                f"https://www.sec.gov/Archives/edgar/data/{int(source['cik'])}/"
                f"{compact}/{source['primary_document']}"
            ),
        })

    mapped = [row for row in rows if row["identity_status"] == "TIME_VALID_MAPPED"]
    ambiguous = [row for row in rows if row["identity_status"] == "AMBIGUOUS"]
    mapped_dates = [date.fromisoformat(row["filing_date"]) for row in mapped]
    mapped_history_years = (
        (max(mapped_dates) - min(mapped_dates)).days / 365.2425
        if len(mapped_dates) >= 2
        else 0.0
    )
    gate = protocol["identity_linkage_gate"]
    checks = {
        "minimum_time_valid_mapped_events": len(mapped)
        >= gate["minimum_time_valid_mapped_events"],
        "minimum_time_valid_mapped_issuers": len({row["cik"] for row in mapped})
        >= gate["minimum_time_valid_mapped_issuers"],
        "minimum_time_valid_history_years": mapped_history_years
        >= gate["minimum_time_valid_history_years"],
        "maximum_ambiguous_event_count": len(ambiguous)
        <= gate["maximum_ambiguous_event_count"],
    }
    linkage_passed = all(checks.values())
    return rows, {
        "report_version": VERSION,
        "status": (
            "IMMUTABLE_CORPUS_READY_FOR_SOURCE_REVIEW"
            if linkage_passed
            else "IMMUTABLE_CORPUS_READY_IDENTITY_EXTENSION_REQUIRED"
        ),
        "protocol_sha256": _sha256(PROTOCOL_PATH),
        "source_event_count": len(rows),
        "source_issuer_count": len({row["cik"] for row in rows}),
        "time_valid_mapped_events": len(mapped),
        "time_valid_mapped_issuers": len({row["cik"] for row in mapped}),
        "time_valid_mapping_ratio": len(mapped) / len(rows),
        "time_valid_history_years": mapped_history_years,
        "ambiguous_event_count": len(ambiguous),
        "unmapped_event_count": sum(row["identity_status"] == "UNMAPPED" for row in rows),
        "checks": checks,
        "identity_linkage_passed": linkage_passed,
        "price_outcomes_opened": False,
        "direction_hypothesis_allowed": False,
        "herd_formula_change_allowed": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
        "next_stage": protocol["next_gate"][
            "if_identity_linkage_passes" if linkage_passed else "if_identity_linkage_fails"
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
    rows, report = build(protocol)
    ledger_path = _rooted(protocol["output"]["ledger"])
    report_path = _rooted(protocol["output"]["report"])
    _write_csv(ledger_path, rows)
    report["ledger_path"] = protocol["output"]["ledger"]
    report["ledger_sha256"] = _sha256(ledger_path)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
