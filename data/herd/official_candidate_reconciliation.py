"""공개 구성 변경 후보를 공식 표·서술 근거와 대조해 상태를 분류한다."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import date
from pathlib import Path


class CandidateReconciliationError(RuntimeError):
    pass


def event_key(row: dict) -> tuple[str, str, str]:
    return row["effective_date"], row["action"], row["ticker"].upper()


def reconcile_candidates(
    candidates: list[dict],
    table_events: list[dict],
    prose_events: list[dict],
    suggestions: list[dict],
    *,
    correction_window_days: int = 7,
) -> tuple[list[dict], dict]:
    table_exact = {event_key(row): row for row in table_events}
    prose_exact = {event_key(row): row for row in prose_events}
    table_by_identity = {}
    for row in table_events:
        table_by_identity.setdefault((row["action"], row["ticker"].upper()), []).append(row)
    suggestion_keys = {event_key(row) for row in suggestions}
    reconciled = []
    for candidate in candidates:
        key = event_key(candidate)
        resolved = None
        status = ""
        if key in table_exact:
            resolved = table_exact[key]
            status = "OFFICIAL_TABLE_EXACT"
        elif key in prose_exact:
            resolved = prose_exact[key]
            status = "OFFICIAL_PROSE_EXACT"
        else:
            same_identity = table_by_identity.get((key[1], key[2]), [])
            nearby = [
                row for row in same_identity
                if abs(
                    (
                        date.fromisoformat(row["effective_date"])
                        - date.fromisoformat(key[0])
                    ).days
                ) <= correction_window_days
            ]
            if len(nearby) == 1:
                resolved = nearby[0]
                status = "CANDIDATE_DATE_CORRECTED_BY_OFFICIAL_TABLE"
            elif same_identity:
                status = "DISTANT_SAME_TICKER_EVENT_REQUIRES_IDENTITY_REVIEW"
            elif key in suggestion_keys:
                status = "OFFICIAL_DOCUMENT_TICKER_ONLY"
            else:
                status = "NO_OFFICIAL_DOCUMENT_MATCH"
        reconciled.append(
            {
                "candidate_effective_date": key[0],
                "action": key[1],
                "ticker": key[2],
                "status": status,
                "resolved_effective_date": resolved["effective_date"] if resolved else "",
                "announcement_date": resolved.get("announcement_date", "") if resolved else "",
                "company_name": resolved.get("company_name", "") if resolved else "",
                "source_url": resolved.get("source_url", "") if resolved else "",
                "source_sha256": resolved.get("source_sha256", "") if resolved else "",
            }
        )
    statuses = Counter(row["status"] for row in reconciled)
    accepted = {
        "OFFICIAL_TABLE_EXACT",
        "OFFICIAL_PROSE_EXACT",
        "CANDIDATE_DATE_CORRECTED_BY_OFFICIAL_TABLE",
    }
    return reconciled, {
        "candidate_events": len(reconciled),
        "statuses": dict(statuses),
        "resolved_events": sum(row["status"] in accepted for row in reconciled),
        "pending_events": sum(row["status"] not in accepted for row in reconciled),
        "complete": bool(reconciled) and all(row["status"] in accepted for row in reconciled),
    }


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_reconciliation(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise CandidateReconciliationError("empty reconciliation")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("table_events", type=Path)
    parser.add_argument("prose_events", type=Path)
    parser.add_argument("suggestions", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows, audit = reconcile_candidates(
        read_csv(args.candidates),
        read_csv(args.table_events),
        read_csv(args.prose_events),
        read_csv(args.suggestions),
    )
    write_reconciliation(args.output, rows)
    print(audit)


if __name__ == "__main__":
    main()
