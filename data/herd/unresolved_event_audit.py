"""미해결 S&P 500 구성 사건을 해결 경로별로 분류하고 감사한다."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

RESOLVED_STATUSES = {
    "OFFICIAL_TABLE_EXACT",
    "OFFICIAL_PROSE_EXACT",
    "CANDIDATE_DATE_CORRECTED_BY_OFFICIAL_TABLE",
    "CANDIDATE_DATE_CORRECTED_BY_OFFICIAL_PROSE",
}

RESOLUTION_LANES = {
    "OFFICIAL_DOCUMENT_TICKER_ONLY": "OFFICIAL_PROSE_OR_TABLE_EXTRACTION",
    "NO_OFFICIAL_DOCUMENT_MATCH": "OFFICIAL_DOCUMENT_DISCOVERY",
    "DISTANT_SAME_TICKER_EVENT_REQUIRES_IDENTITY_REVIEW": "IDENTITY_AND_DATE_CONFLICT",
    "CANDIDATE_ACTION_CONFLICTS_WITH_OFFICIAL_PROSE": "ACTION_CONFLICT_REVIEW",
    "AMBIGUOUS_OFFICIAL_PROSE_SEMANTICS": "AMBIGUOUS_SEMANTICS_REVIEW",
}


class UnresolvedEventAuditError(RuntimeError):
    pass


def _event_key(row: dict) -> tuple[str, str, str]:
    return (
        row["candidate_effective_date"],
        row["action"].upper(),
        row["ticker"].upper(),
    )


def audit_unresolved_events(
    reconciliation: list[dict],
    suggestions: list[dict],
) -> tuple[list[dict], dict]:
    suggestion_counts = Counter(
        (
            row["effective_date"],
            row["action"].upper(),
            row["ticker"].upper(),
        )
        for row in suggestions
    )
    pending = []
    for row in reconciliation:
        status = row["status"]
        if status in RESOLVED_STATUSES:
            continue
        if status not in RESOLUTION_LANES:
            raise UnresolvedEventAuditError(f"unknown reconciliation status: {status}")
        event_date, action, ticker = _event_key(row)
        candidate_date = date.fromisoformat(event_date)
        matches = suggestion_counts[(event_date, action, ticker)]
        pending.append({
            "candidate_effective_date": event_date,
            "action": action,
            "ticker": ticker,
            "reconciliation_status": status,
            "resolution_lane": RESOLUTION_LANES[status],
            "official_document_candidates": matches,
            "candidate_date_is_weekend": candidate_date.weekday() >= 5,
            "target_evidence": (
                "S&P_OFFICIAL_MEMBERSHIP_EVENT_AND_EFFECTIVE_TIMING"
            ),
            "sec_evidence_role": "IDENTITY_OR_CAUSE_ONLY",
            "review_status": "OPEN",
        })

    by_date: dict[str, Counter] = defaultdict(Counter)
    for row in pending:
        by_date[row["candidate_effective_date"]][row["action"]] += 1
    for row in pending:
        counts = by_date[row["candidate_effective_date"]]
        row["same_date_adds"] = counts["ADD"]
        row["same_date_removes"] = counts["REMOVE"]
        row["same_date_action_imbalance"] = counts["ADD"] != counts["REMOVE"]

    lanes = Counter(row["resolution_lane"] for row in pending)
    statuses = Counter(row["reconciliation_status"] for row in pending)
    years = Counter(row["candidate_effective_date"][:4] for row in pending)
    return pending, {
        "candidate_events": len(reconciliation),
        "resolved_events": len(reconciliation) - len(pending),
        "pending_events": len(pending),
        "pending_statuses": dict(sorted(statuses.items())),
        "resolution_lanes": dict(sorted(lanes.items())),
        "pending_by_year": dict(sorted(years.items())),
        "events_with_document_candidates": sum(
            row["official_document_candidates"] > 0 for row in pending
        ),
        "events_without_document_candidates": sum(
            row["official_document_candidates"] == 0 for row in pending
        ),
        "weekend_candidate_dates": sum(
            row["candidate_date_is_weekend"] for row in pending
        ),
        "imbalanced_events": sum(
            row["same_date_action_imbalance"] for row in pending
        ),
        "complete": not pending,
    }


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise UnresolvedEventAuditError("no unresolved events")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reconciliation", type=Path)
    parser.add_argument("suggestions", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows, audit = audit_unresolved_events(
        read_csv(args.reconciliation),
        read_csv(args.suggestions),
    )
    write_csv(args.output, rows)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
