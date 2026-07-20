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
    effective_date = row.get("effective_date") or row.get("candidate_effective_date")
    if not effective_date:
        raise CandidateReconciliationError("candidate effective date is missing")
    return effective_date, row["action"], row["ticker"].upper()


def reconcile_candidates(
    candidates: list[dict],
    table_events: list[dict],
    prose_events: list[dict],
    suggestions: list[dict],
    semantic_events: list[dict] | None = None,
    reviewed_date_corrections: list[dict] | None = None,
    *,
    correction_window_days: int = 7,
) -> tuple[list[dict], dict]:
    table_exact = {event_key(row): row for row in table_events}
    prose_exact = {event_key(row): row for row in prose_events}
    table_by_identity = {}
    for row in table_events:
        table_by_identity.setdefault((row["action"], row["ticker"].upper()), []).append(row)
    suggestion_keys = {event_key(row) for row in suggestions}
    correction_by_candidate = {
        (
            row["candidate_effective_date"],
            row["action"].upper(),
            row["ticker"].upper(),
        ): row
        for row in reviewed_date_corrections or []
    }
    if len(correction_by_candidate) != len(reviewed_date_corrections or []):
        raise CandidateReconciliationError("duplicate reviewed date correction")
    semantic_by_candidate = {}
    for row in semantic_events or []:
        if row["extraction_status"] not in {
            "OFFICIAL_SEMANTICS_MATCH_CANDIDATE",
            "OFFICIAL_SEMANTICS_CONFLICTS_WITH_CANDIDATE",
        }:
            continue
        semantic_key = (
            row["candidate_effective_date"],
            row["candidate_action"],
            row["ticker"].upper(),
        )
        semantic_by_candidate.setdefault(semantic_key, []).append(row)
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
                correction = correction_by_candidate.get(key)
                corrected_date = (
                    correction.get("corrected_effective_date", "")
                    if correction else ""
                )
                matches = [
                    row for row in same_identity
                    if row["effective_date"] == corrected_date
                    and row.get("source_url", "") == correction.get("source_url", "")
                    and row.get("source_sha256", "") == correction.get("source_sha256", "")
                ] if correction else []
                if len(matches) == 1:
                    resolved = matches[0]
                    status = "CANDIDATE_DATE_CORRECTED_BY_REVIEWED_OFFICIAL_TABLE"
                elif correction:
                    raise CandidateReconciliationError(
                        f"reviewed correction does not match archived table event: {key}"
                    )
                else:
                    status = "DISTANT_SAME_TICKER_EVENT_REQUIRES_IDENTITY_REVIEW"
            elif key in semantic_by_candidate:
                semantics = {
                    (
                        row.get("official_action", ""),
                        row.get("membership_session_date", ""),
                        row.get("stated_effective_date", ""),
                        row.get("effective_timing", ""),
                        row.get("source_url", ""),
                        row.get("source_sha256", ""),
                    )
                    for row in semantic_by_candidate[key]
                }
                same_action = {
                    item for item in semantics
                    if item[0] == key[1] and item[1]
                }
                if len(same_action) == 1:
                    (
                        action, membership_date, stated_date, timing,
                        source_url, source_sha256,
                    ) = next(iter(same_action))
                    resolved = {
                        "effective_date": membership_date,
                        "announcement_date": min(
                            row["announcement_date"]
                            for row in semantic_by_candidate[key]
                            if row.get("official_action") == action
                            and row.get("membership_session_date") == membership_date
                        ),
                        "company_name": "",
                        "source_url": source_url,
                        "source_sha256": source_sha256,
                        "stated_effective_date": stated_date,
                        "effective_timing": timing,
                    }
                    status = "CANDIDATE_DATE_CORRECTED_BY_OFFICIAL_PROSE"
                elif any(item[0] and item[0] != key[1] for item in semantics):
                    status = "CANDIDATE_ACTION_CONFLICTS_WITH_OFFICIAL_PROSE"
                else:
                    status = "AMBIGUOUS_OFFICIAL_PROSE_SEMANTICS"
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
                "stated_effective_date": (
                    resolved.get("stated_effective_date", "") if resolved else ""
                ),
                "effective_timing": (
                    resolved.get("effective_timing", "") if resolved else ""
                ),
            }
        )
    statuses = Counter(row["status"] for row in reconciled)
    accepted = {
        "OFFICIAL_TABLE_EXACT",
        "OFFICIAL_PROSE_EXACT",
        "CANDIDATE_DATE_CORRECTED_BY_OFFICIAL_TABLE",
        "CANDIDATE_DATE_CORRECTED_BY_OFFICIAL_PROSE",
        "CANDIDATE_DATE_CORRECTED_BY_REVIEWED_OFFICIAL_TABLE",
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
    parser.add_argument("--semantic-events", type=Path)
    parser.add_argument("--reviewed-date-corrections", type=Path)
    args = parser.parse_args()
    rows, audit = reconcile_candidates(
        read_csv(args.candidates),
        read_csv(args.table_events),
        read_csv(args.prose_events),
        read_csv(args.suggestions),
        read_csv(args.semantic_events) if args.semantic_events else None,
        read_csv(args.reviewed_date_corrections)
        if args.reviewed_date_corrections else None,
    )
    write_reconciliation(args.output, rows)
    print(audit)


if __name__ == "__main__":
    main()
