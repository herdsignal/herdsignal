"""FINRA PIT 식별자 공백 상위 25개 기업을 결과 독립적으로 분류한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_suffix(".json")
QUEUE = ROOT / "data/reports/sec_identifier_gap_queue_v1.csv"
REPORT = ROOT / "data/reports/sec_identifier_gap_queue_v1.json"


class IdentifierGapQueueError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise IdentifierGapQueueError(f"path escapes repository: {relative}")
    return path


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    if resolved.is_relative_to(ROOT.resolve()):
        return resolved.relative_to(ROOT.resolve()).as_posix()
    return resolved.as_posix()


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _locked_path(protocol: dict, role: str) -> Path:
    return _rooted(next(
        row["path"] for row in protocol["locked_inputs"]
        if row["role"] == role
    ))


def _verify_inputs(protocol: dict) -> None:
    for locked in protocol["locked_inputs"]:
        if sha256(_rooted(locked["path"])) != locked["sha256"]:
            raise IdentifierGapQueueError(
                f"locked input changed: {locked['path']}"
            )


def _current_company_metadata(rows: list[dict]) -> dict[str, dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["cik"].zfill(10)].append(row)
    return {
        cik: {
            "company_name": values[0]["company_name"],
            "current_symbols": sorted({
                row["ticker"] for row in values
                if not row["ticker"].startswith(values[0]["ticker"] + "-P")
            }),
        }
        for cik, values in grouped.items()
    }


def _rank_entities(protocol: dict, coverage_rows: list[dict]) -> list[dict]:
    cohort = protocol["selection"]["cohort"]
    candidates = []
    for row in coverage_rows:
        if row["cohort"] != cohort:
            continue
        observed = int(row["observed_settlement_dates"])
        linked = int(row["time_valid_cik_linked_dates"])
        candidates.append({
            **row,
            "cik": row["cik"].zfill(10),
            "observed": observed,
            "linked": linked,
            "unresolved": observed - linked,
        })

    best_by_cik: dict[str, dict] = {}
    cohort_symbols_by_cik: dict[str, set[str]] = defaultdict(set)
    for row in candidates:
        cohort_symbols_by_cik[row["cik"]].add(row["ticker"])
    for row in sorted(
        candidates,
        key=lambda value: (-value["unresolved"], value["ticker"]),
    ):
        if row["cik"] not in best_by_cik:
            best_by_cik[row["cik"]] = {
                **row,
                "cohort_symbols": sorted(cohort_symbols_by_cik[row["cik"]]),
            }
    ranked = [
        row for row in sorted(
            best_by_cik.values(),
            key=lambda value: (-value["unresolved"], value["ticker"]),
        )
        if row["unresolved"] > 0
    ]
    return ranked[:protocol["selection"]["target_entity_count"]]


def _collection_route(classification: str) -> str:
    return {
        "MULTI_CLASS_TAG_COVER_GAP": "PRIMARY_COVER_MULTI_SYMBOL_CONTEXTS",
        "TICKER_REUSE_AND_CURRENT_ISSUER_RENAME": (
            "PRIMARY_COVER_PLUS_COLLISION_BOUNDARY"
        ),
        "CORPORATE_SUCCESSION_NEW_CIK": (
            "SEPARATE_PREDECESSOR_AND_SUCCESSOR_COVER"
        ),
        "FOREIGN_ISSUER_COVER_GAP": "PRIMARY_20F_6K_40F_COVER",
        "SAME_CIK_RENAME": "PRIMARY_COVER_BOTH_SYMBOL_SPANS",
        "PRIMARY_COVER_INTERVAL_GAP": "PRIMARY_COVER_STANDARD_FORMS",
    }[classification]


def build_queue(
    protocol_path: Path = PROTOCOL,
    queue_path: Path = QUEUE,
    report_path: Path = REPORT,
) -> dict:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol["status"] != "LOCKED_BEFORE_TARGETED_COLLECTION_V2":
        raise IdentifierGapQueueError("identifier gap protocol is not locked")
    _verify_inputs(protocol)
    coverage = _read_csv(_locked_path(protocol, "COVERAGE_DETAIL"))
    metadata = _current_company_metadata(
        _read_csv(_locked_path(protocol, "CURRENT_SEC_DISCOVERY_METADATA"))
    )
    ranked = _rank_entities(protocol, coverage)
    if len(ranked) != protocol["selection"]["target_entity_count"]:
        raise IdentifierGapQueueError("insufficient unique identifier gap targets")

    rows = []
    for rank, candidate in enumerate(ranked, start=1):
        cik = candidate["cik"]
        current = metadata.get(cik)
        if current is None:
            raise IdentifierGapQueueError(f"current SEC metadata missing: {cik}")
        override = protocol["classification_overrides"].get(cik, {})
        classification = override.get(
            "classification",
            protocol["default_classification"]["classification"],
        )
        accepted_symbols = override.get(
            "accepted_symbols",
            candidate["cohort_symbols"],
        )
        collection_ciks = sorted({
            cik,
            *override.get("additional_ciks", []),
        })
        rows.append({
            "target_rank": rank,
            "reference_ticker": candidate["ticker"],
            "company_name": current["company_name"],
            "reference_cik": cik,
            "collection_ciks": "|".join(collection_ciks),
            "accepted_symbols": "|".join(accepted_symbols),
            "observed_settlement_dates": candidate["observed"],
            "time_valid_cik_linked_dates": candidate["linked"],
            "unresolved_observed_ticker_dates": candidate["unresolved"],
            "classification": classification,
            "collection_route": _collection_route(classification),
            "boundary_rule": override.get("boundary_rule", ""),
            "selected_without_price_outcomes": True,
        })

    queue_path.parent.mkdir(parents=True, exist_ok=True)
    with queue_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)

    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["classification"]] += 1
    report = {
        "report_version": "SEC_IDENTIFIER_GAP_QUEUE_V1",
        "status": "HASH_LOCKED_TARGET_QUEUE_READY",
        "protocol_sha256": sha256(protocol_path),
        "target_entity_count": len(rows),
        "target_cik_count": len({
            cik for row in rows for cik in row["collection_ciks"].split("|")
        }),
        "unresolved_observed_ticker_dates": sum(
            row["unresolved_observed_ticker_dates"] for row in rows
        ),
        "classification_counts": dict(sorted(counts.items())),
        "queue_path": _display_path(queue_path),
        "queue_sha256": sha256(queue_path),
        "selection_is_price_outcome_independent": True,
        "raw_denominator_is_not_lifecycle_adjusted": True,
        "price_outcomes_opened": False,
        "direction_hypothesis_preregistered": False,
        "herd_formula_change_allowed": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
        "next_priority": "COLLECT_ALL_ELIGIBLE_PRIMARY_COVER_FILINGS_FOR_QUEUE",
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    parser.add_argument("--queue", type=Path, default=QUEUE)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    print(json.dumps(
        build_queue(args.protocol, args.queue, args.report),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
