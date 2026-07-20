"""S&P 공식 변경 근거와 SEC 기업행동 증거를 하나의 감사 원장으로 결합한다."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

RESOLVED_S_AND_P = {
    "OFFICIAL_TABLE_EXACT",
    "OFFICIAL_PROSE_EXACT",
    "CANDIDATE_DATE_CORRECTED_BY_OFFICIAL_TABLE",
    "CANDIDATE_DATE_CORRECTED_BY_OFFICIAL_PROSE",
    "CANDIDATE_DATE_CORRECTED_BY_REVIEWED_OFFICIAL_TABLE",
}
COMMON_FORM25 = {
    "COMMON_EQUITY_FORM25_EVIDENCE",
    "COMMON_EQUITY_INCLUDED_WITH_OTHER_SECURITIES",
}


class IntegratedLedgerError(RuntimeError):
    pass


def candidate_key(row: dict) -> tuple[str, str, str]:
    return (
        row.get("resolved_effective_date") or row["candidate_effective_date"],
        row["action"],
        row["ticker"].upper(),
    )


def event_key(row: dict) -> tuple[str, str, str]:
    return row["effective_date"], row["action"], row["ticker"].upper()


def evidence_event_key(row: dict) -> tuple[str, str]:
    return row["effective_date"], row["ticker"].upper()


def build_integrated_ledger(
    reconciliation: list[dict],
    cik_events: list[dict],
    form25_candidates: list[dict],
    form25_classification: list[dict],
    merger_classification: list[dict],
    identity_transitions: list[dict] | None = None,
    reconstruction_anomalies: list[dict] | None = None,
    continuity_events: list[dict] | None = None,
) -> tuple[list[dict], dict]:
    quarantined_keys = {
        (
            row["candidate_effective_date"],
            row["action"].upper(),
            row["ticker"].upper(),
        )
        for row in reconstruction_anomalies or []
        if str(row.get("exclude_from_official_ledger", "")).lower() == "true"
        or row.get("exclude_from_official_ledger") is True
    }
    cik_by_event = {event_key(row): row for row in cik_events}
    form25_by_url = {
        row["filing_url"]: row["classification_status"]
        for row in form25_classification
    }
    common_form25_events = {
        evidence_event_key(row)
        for row in form25_candidates
        if row.get("filing_url")
        and form25_by_url.get(row["filing_url"]) in COMMON_FORM25
    }
    merger_completion_events = {
        evidence_event_key(row)
        for row in merger_classification
        if row["classification_status"].startswith("MERGER_COMPLETION")
    }
    merger_agreement_events = {
        evidence_event_key(row)
        for row in merger_classification
        if row["classification_status"] == "MERGER_AGREEMENT_EVIDENCE"
    }
    rows = []
    for candidate in reconciliation:
        if candidate["status"] in {
            "VERIFIED_IDENTITY_CHANGE_COMPONENT",
            "VERIFIED_CORPORATE_CONTINUITY_COMPONENT",
        }:
            continue
        source_key = (
            candidate["candidate_effective_date"],
            candidate["action"].upper(),
            candidate["ticker"].upper(),
        )
        if source_key in quarantined_keys:
            continue
        key = candidate_key(candidate)
        official_resolved = candidate["status"] in RESOLVED_S_AND_P
        cik = cik_by_event.get(key)
        corporate_key = (key[0], key[2])
        has_form25 = corporate_key in common_form25_events
        has_merger_completion = corporate_key in merger_completion_events
        has_merger_agreement = corporate_key in merger_agreement_events
        if official_resolved and (has_form25 or has_merger_completion):
            status = "OFFICIAL_EVENT_WITH_SEC_ACTION_EVIDENCE"
        elif official_resolved:
            status = "VERIFIED_OFFICIAL_EVENT"
        elif (
            candidate["status"].startswith("UNMATCHED_")
            or candidate["status"] == "NO_OFFICIAL_DOCUMENT_MATCH"
        ):
            status = "UNRESOLVED"
        else:
            status = "REQUIRES_REVIEW"
        if has_merger_completion:
            cause = "MERGER_OR_ACQUISITION_EVIDENCE"
        elif has_form25:
            cause = "COMMON_EQUITY_DELISTING_EVIDENCE"
        elif has_merger_agreement:
            cause = "MERGER_AGREEMENT_ONLY"
        else:
            cause = "CAUSE_NOT_CONFIRMED"
        rows.append({
            "event_type": "MEMBERSHIP_CHANGE",
            "candidate_effective_date": candidate["candidate_effective_date"],
            "effective_date": key[0] if official_resolved else "",
            "action": key[1],
            "ticker": key[2],
            "company_name": candidate.get("company_name", ""),
            "event_status": status,
            "candidate_reconciliation_status": candidate["status"],
            "cik": cik.get("cik", "") if cik else "",
            "cik_link_status": cik.get("cik_link_status", "") if cik else "",
            "corporate_action_evidence": cause,
            "common_equity_form25": has_form25,
            "merger_completion_evidence": has_merger_completion,
            "merger_agreement_evidence": has_merger_agreement,
            "sp_source_url": candidate.get("source_url", ""),
            "sp_source_sha256": candidate.get("source_sha256", ""),
            "review_status": (
                "REQUIRES_HUMAN_REVIEW"
                if has_form25 or has_merger_completion or has_merger_agreement
                else ""
            ),
        })
    for transition in identity_transitions or []:
        rows.append({
            "event_type": "IDENTITY_CHANGE",
            "candidate_effective_date": transition["new_candidate_date"],
            "effective_date": transition["effective_date"],
            "action": "RENAME",
            "ticker": transition["new_ticker"].upper(),
            "old_ticker": transition["old_ticker"].upper(),
            "company_name": "",
            "event_status": "VERIFIED_IDENTITY_CHANGE",
            "candidate_reconciliation_status": "VERIFIED_IDENTITY_CHANGE_COMPONENT",
            "cik": transition["cik"],
            "cik_link_status": "SEC_SAME_CIK_TRADING_SYMBOL_VERIFIED",
            "corporate_action_evidence": "TICKER_IDENTITY_CONTINUITY",
            "common_equity_form25": False,
            "merger_completion_evidence": False,
            "merger_agreement_evidence": False,
            "sp_source_url": "",
            "sp_source_sha256": "",
            "review_status": "",
        })
    for continuity in continuity_events or []:
        same_cik = continuity["event_type"] in {
            "SAME_CIK_RENAME",
            "SAME_CIK_MEMBERSHIP_CONTINUITY",
        }
        dual_membership = (
            continuity["event_type"] == "SPINOFF_DUAL_MEMBERSHIP_ADDITION"
        )
        rows.append({
            "event_type": "IDENTITY_CHANGE" if same_cik else "MEMBERSHIP_CHANGE",
            "candidate_effective_date": continuity["candidate_effective_date"],
            "effective_date": continuity["effective_date"],
            "action": "RENAME" if same_cik else "ADD",
            "ticker": continuity["ticker"].upper(),
            "old_ticker": continuity["old_ticker"].upper(),
            "company_name": "",
            "event_status": "VERIFIED_CORPORATE_CONTINUITY",
            "candidate_reconciliation_status": (
                "VERIFIED_CORPORATE_CONTINUITY_COMPONENT"
            ),
            "cik": continuity["cik"],
            "cik_link_status": (
                "SEC_SAME_CIK_TRADING_SYMBOL_VERIFIED"
                if same_cik or dual_membership else "SEC_SUCCESSOR_ENTITY_VERIFIED"
            ),
            "corporate_action_evidence": (
                "TICKER_IDENTITY_CONTINUITY"
                if same_cik
                else (
                    "S_AND_P_SPINOFF_DUAL_MEMBERSHIP"
                    if dual_membership
                    else "S_AND_P_MEMBERSHIP_SUCCESSION"
                )
            ),
            "common_equity_form25": False,
            "merger_completion_evidence": not same_cik and not dual_membership,
            "merger_agreement_evidence": False,
            "sp_source_url": continuity.get("sp_source_url", ""),
            "sp_source_sha256": continuity.get("sp_source_sha256", ""),
            "sec_source_url": continuity["sec_source_url"],
            "sec_source_sha256": continuity["sec_source_sha256"],
            "review_status": "",
        })
    statuses = Counter(row["event_status"] for row in rows)
    verified = sum(
        row["event_status"] in {
            "VERIFIED_OFFICIAL_EVENT",
            "OFFICIAL_EVENT_WITH_SEC_ACTION_EVIDENCE",
            "VERIFIED_IDENTITY_CHANGE",
            "VERIFIED_CORPORATE_CONTINUITY",
        }
        for row in rows
    )
    return rows, {
        "candidate_events": len(rows),
        "source_candidate_rows": len(reconciliation),
        "identity_transitions": len(identity_transitions or []),
        "corporate_continuity_events": len(continuity_events or []),
        "quarantined_source_artifacts": len(quarantined_keys),
        "event_statuses": dict(statuses),
        "verified_official_events": verified,
        "events_with_common_form25": sum(row["common_equity_form25"] for row in rows),
        "events_with_merger_completion": sum(
            row["merger_completion_evidence"] for row in rows
        ),
        "replay_ready": bool(rows) and verified == len(rows),
        "survivorship_safe": False,
    }


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise IntegratedLedgerError("integrated ledger is empty")
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
    parser.add_argument("cik_events", type=Path)
    parser.add_argument("form25_candidates", type=Path)
    parser.add_argument("form25_classification", type=Path)
    parser.add_argument("merger_classification", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--identity-transitions", type=Path)
    parser.add_argument("--reconstruction-anomalies", type=Path)
    parser.add_argument("--continuity-events", type=Path)
    args = parser.parse_args()
    rows, audit = build_integrated_ledger(
        read_csv(args.reconciliation),
        read_csv(args.cik_events),
        read_csv(args.form25_candidates),
        read_csv(args.form25_classification),
        read_csv(args.merger_classification),
        read_csv(args.identity_transitions) if args.identity_transitions else None,
        read_csv(args.reconstruction_anomalies)
        if args.reconstruction_anomalies else None,
        read_csv(args.continuity_events) if args.continuity_events else None,
    )
    write_csv(args.output, rows)
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
