"""SEC로 날짜까지 확인된 ticker 변경을 구성 편입·편출 후보에서 분리한다."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path

VERIFIED_IDENTITY = "SEC_IDENTITY_AND_EFFECTIVE_DATE_VERIFIED"


class IdentityTransitionError(RuntimeError):
    pass


def candidate_key(event_date: str, action: str, ticker: str) -> tuple[str, str, str]:
    return event_date, action, ticker.upper()


def reconcile_identity_transitions(
    reconciliation: list[dict],
    identity_evidence: list[dict],
) -> tuple[list[dict], list[dict], dict]:
    verified = [
        row for row in identity_evidence
        if row.get("identity_status") == VERIFIED_IDENTITY
        and row.get("resolved_effective_date")
    ]
    grouped = {}
    for row in verified:
        key = (
            row["candidate_cik"], row["old_ticker"].upper(),
            row["new_ticker"].upper(), row["resolved_effective_date"],
        )
        grouped.setdefault(key, []).append(row)
    complex_groups = {
        (cik, new_ticker, effective_date)
        for cik, _old_ticker, new_ticker, effective_date in grouped
        if len({
            old
            for group_cik, old, group_new, group_date in grouped
            if (
                group_cik == cik
                and group_new == new_ticker
                and group_date == effective_date
            )
        }) > 1
    }
    transitions = []
    consumed = set()
    for (cik, old_ticker, new_ticker, effective_date), matches in grouped.items():
        if (cik, new_ticker, effective_date) in complex_groups:
            continue
        chosen = min(
            matches,
            key=lambda row: (
                abs((
                    date.fromisoformat(row["old_candidate_date"])
                    - date.fromisoformat(effective_date)
                ).days)
                + abs((
                    date.fromisoformat(row["new_candidate_date"])
                    - date.fromisoformat(effective_date)
                ).days),
                row["old_candidate_date"],
                row["new_candidate_date"],
            ),
        )
        old_key = candidate_key(chosen["old_candidate_date"], "REMOVE", old_ticker)
        new_key = candidate_key(chosen["new_candidate_date"], "ADD", new_ticker)
        if old_key in consumed or new_key in consumed:
            continue
        consumed.update((old_key, new_key))
        transitions.append({
            "effective_date": effective_date,
            "event_type": "IDENTITY_CHANGE",
            "cik": cik,
            "old_ticker": old_ticker,
            "new_ticker": new_ticker,
            "old_candidate_date": chosen["old_candidate_date"],
            "new_candidate_date": chosen["new_candidate_date"],
            "identity_status": VERIFIED_IDENTITY,
            "evidence_accessions": chosen.get("evidence_accessions", ""),
        })
    updated = []
    for row in reconciliation:
        key = candidate_key(
            row["candidate_effective_date"], row["action"], row["ticker"]
        )
        if key not in consumed:
            updated.append(dict(row))
            continue
        transition = next(
            item for item in transitions
            if (
                (row["action"] == "REMOVE"
                 and item["old_candidate_date"] == row["candidate_effective_date"]
                 and item["old_ticker"] == row["ticker"].upper())
                or
                (row["action"] == "ADD"
                 and item["new_candidate_date"] == row["candidate_effective_date"]
                 and item["new_ticker"] == row["ticker"].upper())
            )
        )
        updated.append({
            **row,
            "status": "VERIFIED_IDENTITY_CHANGE_COMPONENT",
            "resolved_effective_date": transition["effective_date"],
            "identity_transition_cik": transition["cik"],
        })
    statuses = Counter(row["status"] for row in updated)
    transitions.sort(key=lambda row: (
        row["effective_date"], row["old_ticker"], row["new_ticker"]
    ))
    return updated, transitions, {
        "candidate_events": len(updated),
        "verified_identity_transitions": len(transitions),
        "reclassified_candidate_rows": len(consumed),
        "complex_identity_groups_deferred": len(complex_groups),
        "remaining_non_official_rows": sum(
            row["status"] not in {
                "OFFICIAL_TABLE_EXACT",
                "OFFICIAL_PROSE_EXACT",
                "CANDIDATE_DATE_CORRECTED_BY_OFFICIAL_TABLE",
                "CANDIDATE_DATE_CORRECTED_BY_OFFICIAL_PROSE",
                "VERIFIED_IDENTITY_CHANGE_COMPONENT",
            }
            for row in updated
        ),
        "statuses": dict(statuses),
        "survivorship_safe": False,
    }


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise IdentityTransitionError("empty output")
    fields = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reconciliation", type=Path)
    parser.add_argument("identity_evidence", type=Path)
    parser.add_argument("output_reconciliation", type=Path)
    parser.add_argument("output_transitions", type=Path)
    args = parser.parse_args()
    rows, transitions, audit = reconcile_identity_transitions(
        read_csv(args.reconciliation), read_csv(args.identity_evidence)
    )
    write_csv(args.output_reconciliation, rows)
    write_csv(args.output_transitions, transitions)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
