"""진단 재생 오류를 앞선 미해결 구성·동일성 사건과 연결한다."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path


class ReplayErrorCausalityError(RuntimeError):
    pass


def _prior_cause(error: dict, blockers: list[dict]) -> dict | None:
    ticker = error["ticker"].upper()
    error_date = date.fromisoformat(error["effective_date"])
    candidates = []
    for row in blockers:
        candidate_date = date.fromisoformat(row["candidate_effective_date"])
        if candidate_date >= error_date:
            continue
        row_ticker = row["ticker"].upper()
        introduces_ticker = (
            (row["action"].upper() == "ADD" and row_ticker == ticker)
            or (
                row.get("event_type") == "IDENTITY_CHANGE"
                and row_ticker == ticker
            )
        )
        if introduces_ticker:
            candidates.append((candidate_date, row))
    return max(candidates, default=(None, None), key=lambda item: item[0])[1]


def trace_replay_errors(
    replay_audit: dict,
    ledger: list[dict],
) -> tuple[list[dict], dict]:
    blockers = [
        row for row in ledger
        if row["event_status"] not in {
            "VERIFIED_OFFICIAL_EVENT",
            "OFFICIAL_EVENT_WITH_SEC_ACTION_EVIDENCE",
            "VERIFIED_IDENTITY_CHANGE",
        }
    ]
    rows = []
    for error in replay_audit.get("error_rows", []):
        cause = _prior_cause(error, blockers)
        rows.append({
            "error_effective_date": error["effective_date"],
            "error_type": error["error"],
            "ticker": error["ticker"].upper(),
            "prior_blocker_found": bool(cause),
            "cause_candidate_date": cause.get("candidate_effective_date", "") if cause else "",
            "cause_action": cause.get("action", "") if cause else "",
            "cause_reconciliation_status": (
                cause.get("candidate_reconciliation_status", "") if cause else ""
            ),
            "diagnosis": (
                "DOWNSTREAM_ERROR_FROM_UNRESOLVED_INTRODUCTION"
                if cause else "BASELINE_OR_MISSING_HISTORY_REVIEW_REQUIRED"
            ),
            "auto_fix_allowed": False,
        })
    explained = sum(row["prior_blocker_found"] for row in rows)
    return rows, {
        "replay_errors": len(rows),
        "explained_by_prior_blocker": explained,
        "baseline_or_history_review_required": len(rows) - explained,
        "auto_fixed_errors": 0,
        "replay_ready": False,
    }


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ReplayErrorCausalityError("no replay errors")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replay_json", type=Path)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    replay = json.loads(args.replay_json.read_text(encoding="utf-8"))
    rows, audit = trace_replay_errors(replay["audit"], read_csv(args.ledger))
    write_csv(args.output, rows)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
