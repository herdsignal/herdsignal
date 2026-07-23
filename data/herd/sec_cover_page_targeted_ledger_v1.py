"""SEC periodic cover 앵커를 기존 time-valid ticker–CIK 원장에 안전하게 병합한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from herd.sec_time_valid_ticker_cik_ledger_v2 import canonical_symbol


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_name("sec_cover_page_targeted_ledger_v1.json")
SOURCE_REPORT = ROOT / "data/reports/sec_cover_page_targeted_source_v1.json"
BASE_LEDGER = ROOT / "data/reports/sec_time_valid_ticker_cik_intervals_v2.csv"
LEDGER = ROOT / "data/reports/sec_time_valid_ticker_cik_intervals_v3.csv"
REPORT = ROOT / "data/reports/sec_cover_page_targeted_ledger_v1.json"


class SecCoverLedgerError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _root_path(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise SecCoverLedgerError(f"path escapes repository: {relative}")
    return path


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def verify_source(
    protocol_path: Path = PROTOCOL,
    source_report_path: Path = SOURCE_REPORT,
) -> tuple[dict, dict]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    source = json.loads(source_report_path.read_text(encoding="utf-8"))
    if protocol["status"] != "LOCKED_BEFORE_SOURCE_COLLECTION":
        raise SecCoverLedgerError("targeted cover protocol is not locked")
    if source["protocol_sha256"] != sha256(protocol_path):
        raise SecCoverLedgerError("targeted source protocol lineage mismatch")
    snapshot = _root_path(source["snapshot_path"])
    manifest_path = snapshot / "manifest.json"
    if sha256(manifest_path) != source["snapshot_manifest_sha256"]:
        raise SecCoverLedgerError("targeted source manifest hash mismatch")

    artifacts = [
        *source["submissions_sources"],
        *source["documents"],
        *source["identity_events"],
    ]
    for artifact in artifacts:
        path = (snapshot / artifact["path"]).resolve()
        if not path.is_relative_to(snapshot.resolve()):
            raise SecCoverLedgerError("source artifact escapes snapshot")
        if not path.is_file() or sha256(path) != artifact["sha256"]:
            raise SecCoverLedgerError(
                f"source artifact hash mismatch: {artifact['path']}"
            )
    if source["quarantined_document_count"] != 0:
        raise SecCoverLedgerError("targeted source contains quarantined documents")
    if not all(
        event["required_terms_verified"] for event in source["identity_events"]
    ):
        raise SecCoverLedgerError("identity event terms were not verified")
    return protocol, source


def _anchor_hash(anchors: list[dict]) -> str:
    payload = "\n".join(
        "|".join((
            row["cik"],
            row["symbol"],
            row["filing_date"],
            row["accepted_at"],
            row["accession_number"],
            row["form"],
            row["document_sha256"],
        ))
        for row in anchors
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _split_by_gap(anchors: list[dict], max_gap_days: int) -> list[list[dict]]:
    components: list[list[dict]] = []
    current: list[dict] = []
    for anchor in anchors:
        if current:
            gap = (
                date.fromisoformat(anchor["filing_date"])
                - date.fromisoformat(current[-1]["filing_date"])
            ).days
            if gap > max_gap_days:
                components.append(current)
                current = []
        current.append(anchor)
    if current:
        components.append(current)
    return components


def build_targeted_intervals(protocol: dict, source: dict) -> list[dict]:
    policy = protocol["selection_policy"]
    anchors_by_key: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in source["accepted_anchors"]:
        anchors_by_key[(row["canonical_symbol"], row["cik"])].append(row)

    events = {
        row["ticker"]: row
        for row in source["identity_events"]
        if row["required_terms_verified"]
    }
    intervals = []
    seen_targets: set[tuple[str, str]] = set()
    for target in protocol["targets"]:
        symbol = canonical_symbol(target["resolved_ticker"])
        key = (symbol, target["cik"])
        if key in seen_targets:
            continue
        seen_targets.add(key)
        anchors = sorted(
            {
                (
                    row["filing_date"],
                    row["accession_number"],
                    row["document_sha256"],
                ): row
                for row in anchors_by_key.get(key, [])
            }.values(),
            key=lambda row: (
                row["filing_date"],
                row["accession_number"],
                row["document_sha256"],
            ),
        )
        for component in _split_by_gap(
            anchors, policy["maximum_anchor_gap_days"]
        ):
            if len(component) < policy["minimum_anchor_count_per_interval"]:
                continue
            valid_from = component[0]["filing_date"]
            valid_to = component[-1]["filing_date"]
            boundary_sources = ["SEC_PERIODIC_COVER_PRIMARY_OBSERVATION_SPAN"]
            event = events.get(target["research_ticker"])
            if event and target["cik"] == event["old_cik"]:
                valid_to = event["effective_date"]
                valid_to = (
                    date.fromisoformat(valid_to) - timedelta(days=1)
                ).isoformat()
                boundary_sources.append(
                    f"SEC_PRIMARY_IDENTITY_EVENT:{event['effective_date']}:OLD_CIK"
                )
            if event and target["cik"] == event["new_cik"]:
                valid_from = event["effective_date"]
                boundary_sources.append(
                    f"SEC_PRIMARY_IDENTITY_EVENT:{event['effective_date']}:NEW_CIK"
                )
            valid_from = max(
                valid_from,
                target.get("valid_from", policy["target_start"]),
                policy["target_start"],
            )
            valid_to = min(
                valid_to,
                target.get("valid_to", policy["target_end"]),
                policy["target_end"],
            )
            if valid_from > valid_to:
                continue
            intervals.append({
                "canonical_symbol": symbol,
                "reported_symbols": "|".join(sorted({
                    row["symbol"] for row in component
                })),
                "cik": target["cik"],
                "valid_from": valid_from,
                "valid_to": valid_to,
                "anchor_count": str(len(component)),
                "first_accession": component[0]["accession_number"],
                "last_accession": component[-1]["accession_number"],
                "source_quarters": "SEC_PERIODIC_COVER_PRIMARY",
                "anchor_sha256": _anchor_hash(component),
                "boundary_sources": "|".join(boundary_sources),
                "status": "CANDIDATE",
            })
    return intervals


def _pipe_union(*values: str) -> str:
    return "|".join(sorted({
        part
        for value in values
        for part in value.split("|")
        if part
    }))


def _merge_same_identity(intervals: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in intervals:
        grouped[(row["canonical_symbol"], row["cik"])].append(dict(row))
    merged = []
    for _, rows in sorted(grouped.items()):
        rows.sort(key=lambda row: (row["valid_from"], row["valid_to"]))
        current = rows[0]
        for following in rows[1:]:
            adjacent = (
                date.fromisoformat(following["valid_from"])
                <= date.fromisoformat(current["valid_to"]) + timedelta(days=1)
            )
            if not adjacent:
                merged.append(current)
                current = following
                continue
            lineage = json.dumps(
                sorted((current["anchor_sha256"], following["anchor_sha256"])),
                separators=(",", ":"),
            )
            current["valid_to"] = max(
                current["valid_to"], following["valid_to"]
            )
            current["reported_symbols"] = _pipe_union(
                current["reported_symbols"], following["reported_symbols"]
            )
            current["anchor_count"] = str(
                int(current["anchor_count"]) + int(following["anchor_count"])
            )
            current["first_accession"] = (
                current["first_accession"] or following["first_accession"]
            )
            current["last_accession"] = (
                following["last_accession"] or current["last_accession"]
            )
            current["source_quarters"] = _pipe_union(
                current["source_quarters"], following["source_quarters"]
            )
            current["anchor_sha256"] = hashlib.sha256(
                lineage.encode()
            ).hexdigest()
            current["boundary_sources"] = _pipe_union(
                current["boundary_sources"], following["boundary_sources"]
            )
        merged.append(current)
    return merged


def _mark_conflicts(intervals: list[dict]) -> int:
    by_symbol: dict[str, list[dict]] = defaultdict(list)
    for row in intervals:
        by_symbol[row["canonical_symbol"]].append(row)
    conflicts: set[int] = set()
    for rows in by_symbol.values():
        for position, left in enumerate(rows):
            for right in rows[position + 1:]:
                overlaps = (
                    left["valid_from"] <= right["valid_to"]
                    and right["valid_from"] <= left["valid_to"]
                )
                if left["cik"] != right["cik"] and overlaps:
                    conflicts.update((id(left), id(right)))
    for row in intervals:
        row["status"] = (
            "CONFLICT_EXCLUDED"
            if id(row) in conflicts
            else "TIME_VALID_CIK_VERIFIED"
        )
    return len(conflicts)


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise SecCoverLedgerError("refusing to write empty interval ledger")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def generate(
    protocol_path: Path = PROTOCOL,
    source_report_path: Path = SOURCE_REPORT,
    base_ledger_path: Path = BASE_LEDGER,
    ledger_path: Path = LEDGER,
    report_path: Path = REPORT,
) -> dict:
    protocol, source = verify_source(protocol_path, source_report_path)
    base_rows = _read_csv(base_ledger_path)
    targeted = build_targeted_intervals(protocol, source)
    intervals = _merge_same_identity([*base_rows, *targeted])
    intervals.sort(key=lambda row: (
        row["canonical_symbol"],
        row["valid_from"],
        row["valid_to"],
        row["cik"],
    ))
    conflict_count = _mark_conflicts(intervals)
    _write_csv(ledger_path, intervals)
    verified = [
        row for row in intervals if row["status"] == "TIME_VALID_CIK_VERIFIED"
    ]
    report = {
        "report_version": "SEC_COVER_PAGE_TARGETED_LEDGER_V1",
        "status": "TARGETED_COVER_INTERVALS_MERGED",
        "protocol_sha256": sha256(protocol_path),
        "source_report_sha256": sha256(source_report_path),
        "source_snapshot_manifest_sha256": source[
            "snapshot_manifest_sha256"
        ],
        "base_ledger_path": base_ledger_path.relative_to(ROOT).as_posix(),
        "base_ledger_sha256": sha256(base_ledger_path),
        "targeted_document_count": source["document_count"],
        "targeted_anchor_count": source["accepted_anchor_count"],
        "targeted_interval_count": len(targeted),
        "merged_interval_count": len(intervals),
        "verified_interval_count": len(verified),
        "conflict_excluded_interval_count": conflict_count,
        "verified_canonical_symbol_count": len({
            row["canonical_symbol"] for row in verified
        }),
        "verified_cik_count": len({row["cik"] for row in verified}),
        "cohort_symbol_overrides": protocol["finra_v3_policy"][
            "cohort_symbol_overrides"
        ],
        "bny_linked_to_bny_mellon_cik": False,
        "blackrock_exact_transition_applied": any(
            "SEC_PRIMARY_IDENTITY_EVENT:2024-10-01" in row["boundary_sources"]
            for row in verified
            if row["canonical_symbol"] == "BLK"
        ),
        "ledger_path": ledger_path.relative_to(ROOT).as_posix(),
        "ledger_sha256": sha256(ledger_path),
        "ledger_consumption_rule": "USE_TIME_VALID_CIK_VERIFIED_ROWS_ONLY",
        "full_universe_rescan_performed": False,
        "price_outcomes_opened": False,
        "direction_hypothesis_preregistered": False,
        "herd_formula_change_allowed": False,
        "blind_holdout_access": False,
        "operational_action_authority": False,
        "operational_action_ratio": 0.0,
        "finra_authority": "PROSPECTIVE_SHADOW_OBSERVATION_ONLY",
        "next_priority": "RECALCULATE_FINRA_TIME_VALID_CIK_COVERAGE_WITH_LEDGER_V3",
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    parser.add_argument("--source-report", type=Path, default=SOURCE_REPORT)
    parser.add_argument("--base-ledger", type=Path, default=BASE_LEDGER)
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    print(json.dumps(generate(
        args.protocol,
        args.source_report,
        args.base_ledger,
        args.ledger,
        args.report,
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
