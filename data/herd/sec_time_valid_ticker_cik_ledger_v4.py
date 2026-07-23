"""V2 원장과 표적 SEC cover 앵커를 결합해 시점별 ticker-CIK 원장 V4를 만든다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from herd.sec_time_valid_ticker_cik_ledger_v2 import (
    ROOT,
    _mark_conflicts,
    _split_anchor_components,
    Anchor,
    canonical_symbol,
    sha256,
)


PROTOCOL = Path(__file__).with_suffix(".json")
LEDGER = ROOT / "data/reports/sec_time_valid_ticker_cik_intervals_v4.csv"
REPORT = ROOT / "data/reports/sec_time_valid_ticker_cik_ledger_v4.json"


class SecTickerCikLedgerV4Error(RuntimeError):
    pass


def _root_path(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise SecTickerCikLedgerV4Error(f"path escapes repository: {relative}")
    return path


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _verify_inputs(protocol: dict) -> list[dict]:
    verified = []
    for item in protocol["locked_inputs"]:
        path = _root_path(item["path"])
        actual = sha256(path)
        if actual != item["sha256"]:
            raise SecTickerCikLedgerV4Error(
                f"locked input changed: {item['path']}"
            )
        verified.append({
            "path": item["path"],
            "sha256": actual,
            "role": item["role"],
        })
    cover_report = json.loads(
        _root_path(next(
            item["path"] for item in protocol["locked_inputs"]
            if item["role"] == "TARGETED_COVER_REPORT"
        )).read_text(encoding="utf-8")
    )
    if cover_report["status"] != "HASH_LOCKED_TAGGED_COVER_ANCHORS_READY":
        raise SecTickerCikLedgerV4Error("targeted cover corpus is not ready")
    return verified


def _source_path(protocol: dict, role: str) -> Path:
    return _root_path(next(
        item["path"] for item in protocol["locked_inputs"]
        if item["role"] == role
    ))


def _cover_anchor_hash(anchors: list[Anchor]) -> str:
    payload = "\n".join(
        "|".join((
            row.cik,
            row.reported_symbol,
            row.filing_date.isoformat(),
            row.accession,
            row.form,
            row.source_quarter,
        ))
        for row in anchors
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _cover_intervals(protocol: dict) -> list[dict]:
    policy = protocol["interval_policy"]
    grouped: dict[tuple[str, str], list[Anchor]] = defaultdict(list)
    for row in _read_csv(_source_path(protocol, "TARGETED_COVER_ANCHORS")):
        anchor = Anchor(
            cik=row["cik"].zfill(10),
            reported_symbol=row["reported_symbol"],
            canonical_symbol=canonical_symbol(row["canonical_symbol"]),
            filing_date=date.fromisoformat(row["filing_date"]),
            accession=row["accession_number"],
            form=row["form"],
            source_quarter="SEC_PRIMARY_COVER",
        )
        grouped[(anchor.canonical_symbol, anchor.cik)].append(anchor)

    intervals = []
    for (symbol, cik), anchors in sorted(grouped.items()):
        unique = {
            (row.accession, row.reported_symbol): row for row in anchors
        }
        ordered = sorted(
            unique.values(),
            key=lambda row: (row.filing_date, row.accession, row.reported_symbol),
        )
        components = _split_anchor_components(
            ordered,
            policy["maximum_same_symbol_anchor_gap_days"],
        )
        for component in components:
            if len({row.accession for row in component}) < (
                policy["minimum_distinct_accessions"]
            ):
                continue
            intervals.append({
                "canonical_symbol": symbol,
                "reported_symbols": "|".join(sorted({
                    row.reported_symbol for row in component
                })),
                "cik": cik,
                "valid_from": component[0].filing_date.isoformat(),
                "valid_to": component[-1].filing_date.isoformat(),
                "anchor_count": len(component),
                "first_accession": component[0].accession,
                "last_accession": component[-1].accession,
                "source_quarters": "SEC_PRIMARY_COVER",
                "anchor_sha256": _cover_anchor_hash(component),
                "boundary_sources": (
                    "SEC_PRIMARY_COVER_DEI_TRADING_SYMBOL_AS_FILED_SPAN"
                ),
                "status": "CANDIDATE",
            })
    return intervals


def _v2_intervals(protocol: dict) -> list[dict]:
    rows = _read_csv(_source_path(protocol, "V2_INTERVAL_LEDGER"))
    for row in rows:
        row["status"] = "CANDIDATE"
        row["anchor_count"] = int(row["anchor_count"])
    return rows


def _merge_same_identity(intervals: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in intervals:
        grouped[(row["canonical_symbol"], row["cik"])].append(dict(row))
    merged = []
    for rows in grouped.values():
        ordered = sorted(
            rows,
            key=lambda row: (
                row["valid_from"],
                row["valid_to"],
                row["boundary_sources"],
            ),
        )
        current = None
        for row in ordered:
            if current is None:
                current = row
                continue
            adjacent_limit = (
                date.fromisoformat(current["valid_to"]) + timedelta(days=1)
            )
            if date.fromisoformat(row["valid_from"]) > adjacent_limit:
                merged.append(current)
                current = row
                continue
            current["valid_to"] = max(current["valid_to"], row["valid_to"])
            current["valid_from"] = min(current["valid_from"], row["valid_from"])
            current["reported_symbols"] = "|".join(sorted(
                set(current["reported_symbols"].split("|"))
                | set(row["reported_symbols"].split("|"))
            ))
            current["anchor_count"] += int(row["anchor_count"])
            current["first_accession"] = (
                current["first_accession"] or row["first_accession"]
            )
            current["last_accession"] = (
                row["last_accession"] or current["last_accession"]
            )
            current["source_quarters"] = "|".join(filter(None, sorted(
                set(current["source_quarters"].split("|"))
                | set(row["source_quarters"].split("|"))
            )))
            current["boundary_sources"] = "|".join(filter(None, sorted(
                set(current["boundary_sources"].split("|"))
                | set(row["boundary_sources"].split("|"))
            )))
            current["anchor_sha256"] = hashlib.sha256(
                (
                    current["anchor_sha256"]
                    + "|"
                    + row["anchor_sha256"]
                ).encode()
            ).hexdigest()
        if current is not None:
            merged.append(current)
    return sorted(
        merged,
        key=lambda row: (
            row["canonical_symbol"],
            row["valid_from"],
            row["valid_to"],
            row["cik"],
        ),
    )


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise SecTickerCikLedgerV4Error("refusing to write an empty ledger")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _edge_case_audit(rows: list[dict]) -> dict:
    verified = [
        row for row in rows if row["status"] == "TIME_VALID_CIK_VERIFIED"
    ]
    selected = [
        row for row in verified
        if row["canonical_symbol"] in {
            "BK", "BNY", "BLK", "BRKB", "CRH", "GOOG", "GOOGL"
        }
    ]
    return {
        "target_interval_count": len(selected),
        "target_intervals": [{
            key: row[key] for key in (
                "canonical_symbol",
                "cik",
                "valid_from",
                "valid_to",
                "boundary_sources",
            )
        } for row in selected],
        "bny_historical_ticker_reuse_backfilled": False,
        "blk_different_cik_overlap": any(
            left["cik"] != right["cik"]
            and left["valid_from"] <= right["valid_to"]
            and right["valid_from"] <= left["valid_to"]
            for index, left in enumerate(selected)
            for right in selected[index + 1:]
            if left["canonical_symbol"] == right["canonical_symbol"] == "BLK"
        ),
    }


def generate(
    protocol_path: Path = PROTOCOL,
    ledger_path: Path = LEDGER,
    report_path: Path = REPORT,
) -> dict:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol["status"] != "LOCKED_BEFORE_INTERVAL_GENERATION":
        raise SecTickerCikLedgerV4Error("V4 protocol is not locked")
    verified_inputs = _verify_inputs(protocol)
    v2 = _v2_intervals(protocol)
    cover = _cover_intervals(protocol)
    intervals = _merge_same_identity([*v2, *cover])
    conflict_count = _mark_conflicts(intervals)
    _write_csv(ledger_path, intervals)
    verified = [
        row for row in intervals if row["status"] == "TIME_VALID_CIK_VERIFIED"
    ]
    edge_cases = _edge_case_audit(intervals)
    if edge_cases["blk_different_cik_overlap"]:
        raise SecTickerCikLedgerV4Error("BLK predecessor/successor overlap")
    report = {
        "report_version": "SEC_TIME_VALID_TICKER_CIK_LEDGER_V4",
        "status": "TIME_VALID_TARGETED_COVER_LEDGER_BUILT",
        "protocol_sha256": sha256(protocol_path),
        "integrity": {
            "verified_file_count": len(verified_inputs),
            "files": verified_inputs,
        },
        "v2_candidate_interval_count": len(v2),
        "targeted_cover_interval_count": len(cover),
        "candidate_interval_count": len(intervals),
        "verified_interval_count": len(verified),
        "conflict_excluded_interval_count": conflict_count,
        "verified_canonical_symbol_count": len({
            row["canonical_symbol"] for row in verified
        }),
        "verified_cik_count": len({row["cik"] for row in verified}),
        "edge_case_audit": edge_cases,
        "ledger_path": ledger_path.relative_to(ROOT).as_posix(),
        "ledger_sha256": sha256(ledger_path),
        "ledger_consumption_rule": "USE_TIME_VALID_CIK_VERIFIED_ROWS_ONLY",
        "source_is_not_full_filing_substitute": True,
        "current_ticker_backfill_performed": False,
        "price_outcomes_opened": False,
        "direction_hypothesis_preregistered": False,
        "herd_formula_change_allowed": False,
        "blind_holdout_access": False,
        "operational_action_authority": False,
        "operational_action_ratio": 0.0,
        "finra_authority": "PROSPECTIVE_SHADOW_OBSERVATION_ONLY",
        "next_priority": (
            "REAUDIT_FINRA_COVERAGE_WITH_ISSUE_NAME_SAFE_BNY_HANDLING"
        ),
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    result = generate(args.protocol, args.ledger, args.report)
    print(json.dumps({
        "status": result["status"],
        "targeted_cover_interval_count": result["targeted_cover_interval_count"],
        "verified_interval_count": result["verified_interval_count"],
        "conflict_excluded_interval_count": (
            result["conflict_excluded_interval_count"]
        ),
        "edge_case_audit": result["edge_case_audit"],
        "next_priority": result["next_priority"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
