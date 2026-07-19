"""검증된 S&P 이벤트를 기준 구성에 재생하고 불완전 원장은 차단한다."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from datetime import date


class ConstituentReplayError(RuntimeError):
    pass


VERIFIED_STATUSES = {
    "VERIFIED_OFFICIAL_EVENT",
    "OFFICIAL_EVENT_WITH_SEC_ACTION_EVIDENCE",
}


def replay_events(
    baseline: set[str],
    ledger: list[dict],
    *,
    allow_diagnostic: bool = False,
    minimum_size: int = 480,
    maximum_size: int = 510,
) -> tuple[list[dict], dict]:
    blockers = [
        row for row in ledger if row["event_status"] not in VERIFIED_STATUSES
    ]
    if blockers and not allow_diagnostic:
        raise ConstituentReplayError(
            f"integrated ledger has {len(blockers)} unresolved/review events"
        )
    current = {ticker.upper() for ticker in baseline}
    events_by_date = defaultdict(list)
    for row in ledger:
        if row["event_status"] in VERIFIED_STATUSES and row.get("effective_date"):
            events_by_date[row["effective_date"]].append(row)
    snapshots = []
    errors = []
    for effective, events in sorted(events_by_date.items()):
        before = set(current)
        for event in sorted(events, key=lambda row: row["action"], reverse=True):
            ticker = event["ticker"].upper()
            if event["action"] == "REMOVE":
                if ticker not in current:
                    errors.append({
                        "effective_date": effective,
                        "error": "REMOVE_ABSENT_TICKER",
                        "ticker": ticker,
                    })
                else:
                    current.remove(ticker)
            elif ticker in current:
                errors.append({
                    "effective_date": effective,
                    "error": "ADD_EXISTING_TICKER",
                    "ticker": ticker,
                })
            else:
                current.add(ticker)
        if not minimum_size <= len(current) <= maximum_size:
            errors.append({
                "effective_date": effective,
                "error": "CONSTITUENT_COUNT_OUTSIDE_GATE",
                "ticker": "",
                "count": len(current),
            })
        snapshots.append({
            "effective_date": effective,
            "before_count": len(before),
            "after_count": len(current),
            "added": sorted(current - before),
            "removed": sorted(before - current),
        })
    return snapshots, {
        "baseline_count": len(baseline),
        "verified_events": sum(len(rows) for rows in events_by_date.values()),
        "blocked_events": len(blockers),
        "effective_dates": len(events_by_date),
        "final_count": len(current),
        "errors": len(errors),
        "error_types": dict(Counter(row["error"] for row in errors)),
        "error_rows": errors,
        "diagnostic_only": bool(blockers) or allow_diagnostic,
        "replay_complete": not blockers and not errors,
    }


def load_baseline_from_intervals(path, as_of: date) -> set[str]:
    import gzip
    opener = gzip.open if str(path).endswith(".gz") else open
    tickers = set()
    with opener(path, "rt", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            start = date.fromisoformat(row["effective_from"])
            end = date.fromisoformat(row["effective_to"]) if row["effective_to"] else None
            if start <= as_of and (end is None or as_of < end):
                tickers.add(row["ticker"].upper())
    return tickers
