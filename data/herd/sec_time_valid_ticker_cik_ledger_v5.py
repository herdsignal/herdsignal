"""V4 원장과 SEC 표지 corpus V2를 결합해 lifecycle-safe V5를 만든다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

from herd.sec_time_valid_ticker_cik_ledger_v2 import (
    Anchor,
    _mark_conflicts,
    _split_anchor_components,
    canonical_symbol,
    sha256,
)
from herd.sec_time_valid_ticker_cik_ledger_v4 import _merge_same_identity


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_suffix(".json")
LEDGER = ROOT / "data/reports/sec_time_valid_ticker_cik_intervals_v5.csv"
REPORT = ROOT / "data/reports/sec_time_valid_ticker_cik_ledger_v5.json"


class SecTickerCikLedgerV5Error(RuntimeError):
    pass


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise SecTickerCikLedgerV5Error(f"path escapes repository: {relative}")
    return path


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    if resolved.is_relative_to(ROOT.resolve()):
        return resolved.relative_to(ROOT.resolve()).as_posix()
    return resolved.as_posix()


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _source(protocol: dict, role: str) -> Path:
    return _rooted(next(
        row["path"] for row in protocol["locked_inputs"]
        if row["role"] == role
    ))


def _verify_inputs(protocol: dict) -> None:
    for item in protocol["locked_inputs"]:
        if sha256(_rooted(item["path"])) != item["sha256"]:
            raise SecTickerCikLedgerV5Error(
                f"locked input changed: {item['path']}"
            )
    cover_report = json.loads(
        _source(protocol, "TARGETED_COVER_V2_REPORT").read_text(
            encoding="utf-8"
        )
    )
    if cover_report["status"] != "HASH_LOCKED_ELIGIBLE_SOURCE_EXHAUSTED":
        raise SecTickerCikLedgerV5Error("V2 cover corpus is not complete")


def _anchor_digest(anchors: list[Anchor]) -> str:
    return hashlib.sha256("\n".join(
        "|".join((
            row.cik,
            row.reported_symbol,
            row.filing_date.isoformat(),
            row.accession,
            row.form,
        ))
        for row in anchors
    ).encode()).hexdigest()


def _intervals_from_anchors(
    anchors: list[Anchor],
    policy: dict,
    source: str,
) -> list[dict]:
    grouped: dict[tuple[str, str], list[Anchor]] = defaultdict(list)
    for anchor in anchors:
        grouped[(anchor.canonical_symbol, anchor.cik)].append(anchor)
    intervals = []
    for (symbol, cik), values in sorted(grouped.items()):
        unique = {
            (row.accession, row.reported_symbol): row for row in values
        }
        ordered = sorted(
            unique.values(),
            key=lambda row: (row.filing_date, row.accession),
        )
        for component in _split_anchor_components(
            ordered,
            policy["maximum_same_symbol_anchor_gap_days"],
        ):
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
                "source_quarters": "SEC_PRIMARY_COVER_V2",
                "anchor_sha256": _anchor_digest(component),
                "boundary_sources": source,
                "status": "CANDIDATE",
            })
    return intervals


def _v4_intervals(protocol: dict) -> list[dict]:
    rows = _read_csv(_source(protocol, "V4_INTERVAL_LEDGER"))
    for row in rows:
        row["anchor_count"] = int(row["anchor_count"])
        row["status"] = "CANDIDATE"
    return rows


def _v2_accepted_anchors(protocol: dict) -> list[Anchor]:
    return [
        Anchor(
            cik=row["cik"].zfill(10),
            reported_symbol=row["reported_symbol"],
            canonical_symbol=canonical_symbol(row["canonical_symbol"]),
            filing_date=date.fromisoformat(row["filing_date"]),
            accession=row["accession_number"],
            form=row["form"],
            source_quarter="SEC_PRIMARY_COVER_V2",
        )
        for row in _read_csv(_source(protocol, "TARGETED_COVER_V2_ANCHORS"))
    ]


def _explicit_predecessor_anchors(protocol: dict) -> list[Anchor]:
    catalog = _read_csv(_source(protocol, "TARGETED_COVER_V2_CATALOG"))
    anchors = []
    for rule in protocol["explicit_predecessor_symbol_rules"].values():
        cik = rule["cik"]
        predecessor = rule["predecessor_symbol"]
        successor = rule["successor_symbol"]
        successor_dates = [
            row["filing_date"] for row in catalog
            if row["cik"] == cik
            and successor in row["tagged_symbols"].split("|")
        ]
        if not successor_dates:
            raise SecTickerCikLedgerV5Error(
                f"successor symbol has no tagged anchor: {successor}"
            )
        first_successor = min(successor_dates)
        for row in catalog:
            if (
                row["cik"] == cik
                and row["filing_date"] < first_successor
                and predecessor in row["tagged_symbols"].split("|")
            ):
                anchors.append(Anchor(
                    cik=cik,
                    reported_symbol=predecessor,
                    canonical_symbol=canonical_symbol(predecessor),
                    filing_date=date.fromisoformat(row["filing_date"]),
                    accession=row["accession_number"],
                    form=row["form"],
                    source_quarter="SEC_PRIMARY_COVER_V2_EXPLICIT_PREDECESSOR",
                ))
    return anchors


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise SecTickerCikLedgerV5Error("refusing to write empty V5 ledger")
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

    def intervals(symbol: str) -> list[dict]:
        return [
            row for row in verified
            if row["canonical_symbol"] == canonical_symbol(symbol)
        ]

    def no_different_cik_overlap(symbol: str) -> bool:
        selected = intervals(symbol)
        return not any(
            left["cik"] != right["cik"]
            and left["valid_from"] <= right["valid_to"]
            and right["valid_from"] <= left["valid_to"]
            for index, left in enumerate(selected)
            for right in selected[index + 1:]
        )

    return {
        "fox_classes_present": all(intervals(symbol) for symbol in ("FOX", "FOXA")),
        "news_classes_present": all(intervals(symbol) for symbol in ("NWS", "NWSA")),
        "bg_predecessor_successor_nonoverlap": no_different_cik_overlap("BG"),
        "doc_ticker_reuse_nonoverlap": no_different_cik_overlap("DOC"),
        "cor_ticker_reuse_nonoverlap": no_different_cik_overlap("COR"),
        "echo_ticker_reuse_nonoverlap": no_different_cik_overlap("ECHO"),
        "cohr_predecessor_symbol_present": any(
            row["cik"] == "0000820318" for row in intervals("IIVI")
        ),
    }


def generate(
    protocol_path: Path = PROTOCOL,
    ledger_path: Path = LEDGER,
    report_path: Path = REPORT,
) -> dict:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol["status"] != "LOCKED_BEFORE_LIFECYCLE_LEDGER_GENERATION":
        raise SecTickerCikLedgerV5Error("V5 protocol is not locked")
    _verify_inputs(protocol)
    policy = protocol["interval_policy"]
    accepted = _intervals_from_anchors(
        _v2_accepted_anchors(protocol),
        policy,
        "SEC_PRIMARY_COVER_V2_TAGGED_ACCEPTED_SYMBOL_SPAN",
    )
    predecessor = _intervals_from_anchors(
        _explicit_predecessor_anchors(protocol),
        policy,
        "SEC_PRIMARY_COVER_V2_EXPLICIT_PREDECESSOR_SYMBOL_SPAN",
    )
    intervals = _merge_same_identity([
        *_v4_intervals(protocol),
        *accepted,
        *predecessor,
    ])
    conflict_count = _mark_conflicts(intervals)
    _write_csv(ledger_path, intervals)
    verified = [
        row for row in intervals if row["status"] == "TIME_VALID_CIK_VERIFIED"
    ]
    edge_cases = _edge_case_audit(intervals)
    if not all(edge_cases.values()):
        raise SecTickerCikLedgerV5Error(
            f"V5 identity edge-case audit failed: {edge_cases}"
        )
    cover_report = json.loads(
        _source(protocol, "TARGETED_COVER_V2_REPORT").read_text(
            encoding="utf-8"
        )
    )
    report = {
        "report_version": "SEC_TIME_VALID_TICKER_CIK_LEDGER_V5",
        "status": "TIME_VALID_LIFECYCLE_LEDGER_BUILT",
        "protocol_sha256": sha256(protocol_path),
        "v4_interval_count": len(_v4_intervals(protocol)),
        "v2_accepted_interval_count": len(accepted),
        "v2_explicit_predecessor_interval_count": len(predecessor),
        "targeted_filing_count": cover_report["filing_count"],
        "targeted_anchor_count": cover_report["anchor_count"],
        "targeted_entity_count": cover_report["target_entity_count"],
        "candidate_interval_count": len(intervals),
        "verified_interval_count": len(verified),
        "conflict_excluded_interval_count": conflict_count,
        "verified_canonical_symbol_count": len({
            row["canonical_symbol"] for row in verified
        }),
        "verified_cik_count": len({row["cik"] for row in verified}),
        "edge_case_audit": edge_cases,
        "ledger_path": _display_path(ledger_path),
        "ledger_sha256": sha256(ledger_path),
        "current_ticker_backfill_performed": False,
        "interval_extrapolation_performed": False,
        "price_outcomes_opened": False,
        "direction_hypothesis_preregistered": False,
        "herd_formula_change_allowed": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
        "next_priority": "AUDIT_FINRA_WITH_IDENTITY_OBSERVED_LIFECYCLE_DENOMINATOR",
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
    print(json.dumps(
        generate(args.protocol, args.ledger, args.report),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
