"""미해결 S&P 후보를 서로 다른 증명 책임을 가진 네 경로로 분리한다."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

RESOLVED_STATUSES = {
    "OFFICIAL_TABLE_EXACT",
    "OFFICIAL_PROSE_EXACT",
    "CANDIDATE_DATE_CORRECTED_BY_OFFICIAL_TABLE",
    "CANDIDATE_DATE_CORRECTED_BY_OFFICIAL_PROSE",
    "VERIFIED_IDENTITY_CHANGE_COMPONENT",
}

ACTUAL_MEMBERSHIP_CHANGE = "ACTUAL_MEMBERSHIP_CHANGE_REQUIRES_OFFICIAL_SEMANTICS"
UNCONFIRMED_IDENTITY_CHANGE = "UNCONFIRMED_TICKER_CHANGE"
RECONSTRUCTION_ANOMALY = "PUBLIC_RECONSTRUCTION_ANOMALY"
MISSING_OFFICIAL_DOCUMENT = "OFFICIAL_DOCUMENT_MISSING"


class ResidualEventClassificationError(RuntimeError):
    pass


def _candidate_key(row: dict) -> tuple[str, str, str]:
    return (
        row["candidate_effective_date"],
        row["action"].upper(),
        row["ticker"].upper(),
    )


def _normalized_ticker(ticker: str) -> str:
    ticker = re.sub(r"\s*\(PREVIOUSLY[^)]*\)\s*", "", ticker.upper())
    return re.sub(r"[^A-Z0-9]", "", ticker)


def _identity_component_keys(identity_evidence: list[dict]) -> set[tuple[str, str, str]]:
    keys = set()
    for row in identity_evidence:
        if row.get("identity_status") != "SEC_SAME_CIK_IDENTITY_DATE_UNVERIFIED":
            continue
        old_ticker = row.get("old_ticker", "").upper()
        new_ticker = row.get("new_ticker", "").upper()
        old_date = row.get("old_candidate_date", "")
        new_date = row.get("new_candidate_date", "")
        if old_ticker and old_date:
            keys.add((old_date, "REMOVE", old_ticker))
        if new_ticker and new_date:
            keys.add((new_date, "ADD", new_ticker))
    return keys


def _anomaly_keys(rows: list[dict], *, proximity_days: int = 7) -> set[tuple[str, str, str]]:
    pending = [row for row in rows if row["status"] not in RESOLVED_STATUSES]
    keys = set()
    for index, left in enumerate(pending):
        left_key = _candidate_key(left)
        left_date = date.fromisoformat(left_key[0])
        left_normalized = _normalized_ticker(left_key[2])
        if "PREVIOUSLY" in left_key[2]:
            keys.add(left_key)
        for right in pending[index + 1:]:
            right_key = _candidate_key(right)
            if left_key[1] == right_key[1]:
                continue
            if _normalized_ticker(right_key[2]) != left_normalized:
                continue
            gap = abs((date.fromisoformat(right_key[0]) - left_date).days)
            if gap <= proximity_days:
                keys.update((left_key, right_key))
    return keys


def classify_residual_events(
    reconciliation: list[dict],
    identity_evidence: list[dict],
) -> tuple[list[dict], dict]:
    identity_keys = _identity_component_keys(identity_evidence)
    anomaly_keys = _anomaly_keys(reconciliation)
    rows = []
    for source in reconciliation:
        if source["status"] in RESOLVED_STATUSES:
            continue
        key = _candidate_key(source)
        if key in anomaly_keys:
            category = RECONSTRUCTION_ANOMALY
            required_evidence = "SOURCE_CORRECTION_OR_INDEPENDENT_OFFICIAL_EVENT"
        elif key in identity_keys:
            category = UNCONFIRMED_IDENTITY_CHANGE
            required_evidence = "SEC_SAME_CIK_AND_EXACT_SYMBOL_EFFECTIVE_DATE"
        elif source["status"] in {
            "OFFICIAL_DOCUMENT_TICKER_ONLY",
            "CANDIDATE_ACTION_CONFLICTS_WITH_OFFICIAL_PROSE",
            "DISTANT_SAME_TICKER_EVENT_REQUIRES_IDENTITY_REVIEW",
        }:
            category = ACTUAL_MEMBERSHIP_CHANGE
            required_evidence = "S&P_ACTION_AND_MEMBERSHIP_SESSION_SEMANTICS"
        elif source["status"] == "NO_OFFICIAL_DOCUMENT_MATCH":
            category = MISSING_OFFICIAL_DOCUMENT
            required_evidence = "S&P_OFFICIAL_DOCUMENT_URL_AND_SHA256"
        else:
            raise ResidualEventClassificationError(
                f"unsupported reconciliation status: {source['status']}"
            )
        rows.append({
            "candidate_effective_date": key[0],
            "action": key[1],
            "ticker": key[2],
            "reconciliation_status": source["status"],
            "residual_category": category,
            "required_evidence": required_evidence,
            "promotion_allowed": False,
            "review_status": "OPEN",
        })
    counts = Counter(row["residual_category"] for row in rows)
    return rows, {
        "residual_events": len(rows),
        "categories": dict(sorted(counts.items())),
        "promotion_allowed_events": 0,
        "classification_complete": bool(rows) and sum(counts.values()) == len(rows),
        "replay_ready": False,
        "survivorship_safe": False,
    }


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ResidualEventClassificationError("no residual events")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reconciliation", type=Path)
    parser.add_argument("identity_evidence", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows, audit = classify_residual_events(
        read_csv(args.reconciliation), read_csv(args.identity_evidence)
    )
    write_csv(args.output, rows)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
