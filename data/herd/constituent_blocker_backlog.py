"""통합 원장의 미해결 사건을 증명 경로별 작업 대기열로 분리한다."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path

VERIFIED_EVENT_STATUSES = {
    "VERIFIED_OFFICIAL_EVENT",
    "OFFICIAL_EVENT_WITH_SEC_ACTION_EVIDENCE",
    "VERIFIED_IDENTITY_CHANGE",
    "VERIFIED_CORPORATE_CONTINUITY",
}
OFFICIAL_SEMANTICS_CATEGORY = (
    "ACTUAL_MEMBERSHIP_CHANGE_REQUIRES_OFFICIAL_SEMANTICS"
)
ROUTED_WORKSTREAMS = {
    "HISTORICAL_TICKER_ALIAS_REQUIRED": (
        "TICKER_ALIAS_NORMALIZATION",
        "VERIFIED_TICKER_HISTORY_AND_EFFECTIVE_INTERVAL",
        "P0",
    ),
    "MULTI_CLASS_NORMALIZATION_REQUIRED": (
        "SHARE_CLASS_NORMALIZATION",
        "OFFICIAL_MULTI_CLASS_SYMBOL_EXPRESSION",
        "P0",
    ),
    "CORPORATE_ACTION_CHAIN_REQUIRED": (
        "CORPORATE_ACTION_CHAIN_RECONSTRUCTION",
        "S&P_MEMBERSHIP_AND_SEC_CORPORATE_ACTION_TIMELINE",
        "P0",
    ),
    "PUBLIC_RECONSTRUCTION_ANOMALY": (
        "SOURCE_ANOMALY_QUARANTINE",
        "SOURCE_CORRECTION_OR_INDEPENDENT_OFFICIAL_EVENT",
        "P0",
    ),
    "OFFICIAL_SOURCE_GAP": (
        "OFFICIAL_DOCUMENT_DISCOVERY",
        "S&P_RELEASE_OR_INDEX_ANNOUNCEMENT_URL_AND_SHA256",
        "P1",
    ),
    "EVIDENCE_TRIAGE_REQUIRED": (
        "EVIDENCE_ROUTE_TRIAGE",
        "CLASSIFY_BEFORE_EVIDENCE_COLLECTION",
        "P1",
    ),
}


class BlockerBacklogError(RuntimeError):
    pass


def _key(row: dict) -> tuple[str, str, str]:
    return (
        row["candidate_effective_date"],
        row["action"].upper(),
        row["ticker"].upper(),
    )


def build_blocker_backlog(
    ledger: list[dict],
    residual_classification: list[dict],
    *,
    identity_evidence: list[dict] | None = None,
    pair_window_days: int = 3,
) -> tuple[list[dict], dict]:
    blockers = [
        row for row in ledger
        if row["event_status"] not in VERIFIED_EVENT_STATUSES
    ]
    residual_by_key = {_key(row): row for row in residual_classification}
    blocker_keys = {_key(row) for row in blockers}
    if len(blocker_keys) != len(blockers):
        raise BlockerBacklogError("duplicate blocker event")
    missing = sorted(blocker_keys - residual_by_key.keys())
    if missing:
        raise BlockerBacklogError(f"blockers missing classification: {missing}")

    dated = [
        (date.fromisoformat(row["candidate_effective_date"]), row)
        for row in blockers
    ]
    verified_identity_keys = set()
    for identity in identity_evidence or []:
        if identity.get("identity_status") != "SEC_IDENTITY_AND_EFFECTIVE_DATE_VERIFIED":
            continue
        old_ticker = identity.get("old_ticker", "").upper()
        new_ticker = identity.get("new_ticker", "").upper()
        old_date = identity.get("old_candidate_date", "")
        new_date = identity.get("new_candidate_date", "")
        if old_ticker and old_date:
            verified_identity_keys.add((old_date, "REMOVE", old_ticker))
        if new_ticker and new_date:
            verified_identity_keys.add((new_date, "ADD", new_ticker))
    rows = []
    for event_date, source in dated:
        key = _key(source)
        residual = residual_by_key[key]
        opposite = [
            other for other_date, other in dated
            if other["action"].upper() != source["action"].upper()
            and abs((other_date - event_date).days) <= pair_window_days
        ]
        if residual["residual_category"] in ROUTED_WORKSTREAMS:
            workstream, evidence, priority = ROUTED_WORKSTREAMS[
                residual["residual_category"]
            ]
        elif residual["residual_category"] == OFFICIAL_SEMANTICS_CATEGORY:
            workstream = "OFFICIAL_MEMBERSHIP_SEMANTICS_REVIEW"
            evidence = "S&P_ACTION_EFFECTIVE_SESSION_AND_MEMBERSHIP_LANGUAGE"
            priority = "P0"
        elif key in verified_identity_keys:
            workstream = "CORPORATE_ACTION_CONTINUITY_REVIEW"
            evidence = "SEC_CIK_TICKER_OR_MERGER_EVIDENCE_AND_S&P_CONTINUITY"
            priority = "P1"
        elif opposite:
            workstream = "PROXIMITY_PAIR_TRIAGE"
            evidence = "COMPANY_IDENTITY_BEFORE_CORPORATE_ACTION_REVIEW"
            priority = "P2"
        else:
            workstream = "OFFICIAL_DOCUMENT_DISCOVERY"
            evidence = "S&P_RELEASE_OR_INDEX_ANNOUNCEMENT_URL_AND_SHA256"
            priority = "P2"
        rows.append({
            "candidate_effective_date": key[0],
            "action": key[1],
            "ticker": key[2],
            "event_status": source["event_status"],
            "residual_category": residual["residual_category"],
            "workstream": workstream,
            "priority": priority,
            "paired_opposite_candidates": "|".join(sorted({
                f"{other['candidate_effective_date']}:{other['action']}:{other['ticker']}"
                for other in opposite
            })),
            "required_evidence": evidence,
            "promotion_allowed": "false",
        })
    rows.sort(key=lambda row: (
        row["priority"],
        row["candidate_effective_date"],
        row["action"],
        row["ticker"],
    ))
    workstreams = Counter(row["workstream"] for row in rows)
    priorities = Counter(row["priority"] for row in rows)
    return rows, {
        "ledger_blockers": len(blockers),
        "classified_blockers": len(rows),
        "workstreams": dict(sorted(workstreams.items())),
        "priorities": dict(sorted(priorities.items())),
        "unclassified_blockers": 0,
        "promotion_allowed_events": 0,
        "replay_ready": False,
        "survivorship_safe": False,
    }


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("integrated_ledger", type=Path)
    parser.add_argument("residual_classification", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--identity-evidence", type=Path)
    args = parser.parse_args()
    rows, audit = build_blocker_backlog(
        read_csv(args.integrated_ledger),
        read_csv(args.residual_classification),
        identity_evidence=(
            read_csv(args.identity_evidence) if args.identity_evidence else None
        ),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
