"""검증된 S&P 이벤트를 기준 구성에 재생하고 불완전 원장은 차단한다."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import date


class ConstituentReplayError(RuntimeError):
    pass


VERIFIED_STATUSES = {
    "VERIFIED_OFFICIAL_EVENT",
    "OFFICIAL_EVENT_WITH_SEC_ACTION_EVIDENCE",
    "VERIFIED_IDENTITY_CHANGE",
    "VERIFIED_CORPORATE_CONTINUITY",
}
VERIFIED_BASELINE_STATUS = "VERIFIED_BASELINE_CONTINUITY_BACKCAST"
DEFAULT_EVENT_SEQUENCE = {
    "REMOVE": 10,
    "ADD": 20,
    "SUCCESSION": 25,
    "RENAME": 30,
}


def apply_baseline_corrections(
    baseline: set[str],
    corrections: list[dict],
    *,
    as_of: date,
) -> tuple[set[str], dict]:
    corrected = {ticker.upper() for ticker in baseline}
    applied = []
    for row in corrections:
        if row.get("event_status") != VERIFIED_BASELINE_STATUS:
            raise ConstituentReplayError("unverified baseline correction")
        if row.get("promotion_scope") != "DIAGNOSTIC_BASELINE_ONLY":
            raise ConstituentReplayError("baseline correction scope must remain diagnostic")
        if row.get("inference") != "true":
            raise ConstituentReplayError("baseline correction must disclose inference")
        correction_date = date.fromisoformat(row["as_of"])
        if correction_date > as_of:
            continue
        ticker = row["ticker"].upper()
        if row["action"] != "ADD" or ticker in corrected:
            raise ConstituentReplayError(f"invalid baseline correction: {ticker}")
        corrected.add(ticker)
        applied.append(ticker)
    return corrected, {
        "baseline_count_raw": len(baseline),
        "baseline_corrections": len(applied),
        "baseline_correction_tickers": sorted(applied),
        "baseline_correction_scope": "DIAGNOSTIC_BASELINE_ONLY",
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
        index_date = row.get("index_effective_date") or row.get("effective_date")
        if row["event_status"] in VERIFIED_STATUSES and index_date:
            events_by_date[index_date].append(row)
    snapshots = []
    errors = []
    for effective, events in sorted(events_by_date.items()):
        before = set(current)
        for event in sorted(
            events,
            key=lambda row: (
                int(
                    row.get("event_sequence")
                    or DEFAULT_EVENT_SEQUENCE.get(row["action"], 99)
                ),
                row["ticker"],
            ),
        ):
            ticker = event["ticker"].upper()
            if event.get("event_type") in {
                "IDENTITY_CHANGE",
                "CORPORATE_SUCCESSION",
            }:
                old_tickers = [
                    value.strip().upper()
                    for value in event.get("old_ticker", "").split("|")
                    if value.strip()
                ]
                absent = [value for value in old_tickers if value not in current]
                if not old_tickers or absent:
                    errors.append({
                        "effective_date": effective,
                        "error": "RENAME_ABSENT_OLD_TICKER",
                        "ticker": "|".join(absent or old_tickers),
                    })
                elif ticker in current and ticker not in old_tickers:
                    errors.append({
                        "effective_date": effective,
                        "error": "RENAME_EXISTING_NEW_TICKER",
                        "ticker": ticker,
                    })
                else:
                    current.difference_update(old_tickers)
                    current.add(ticker)
            elif event["action"] == "REMOVE":
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


def read_csv(path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline_intervals")
    parser.add_argument("ledger")
    parser.add_argument("output")
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--baseline-corrections")
    args = parser.parse_args()
    baseline = load_baseline_from_intervals(args.baseline_intervals, args.as_of)
    correction_audit = {}
    if args.baseline_corrections:
        baseline, correction_audit = apply_baseline_corrections(
            baseline,
            read_csv(args.baseline_corrections),
            as_of=args.as_of,
        )
    snapshots, audit = replay_events(
        baseline, read_csv(args.ledger), allow_diagnostic=args.diagnostic
    )
    audit.update(correction_audit)
    if correction_audit.get("baseline_corrections"):
        audit["diagnostic_only"] = True
        audit["replay_complete"] = False
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(
            {"audit": audit, "snapshots": snapshots},
            handle, ensure_ascii=False, indent=2,
        )
        handle.write("\n")
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
