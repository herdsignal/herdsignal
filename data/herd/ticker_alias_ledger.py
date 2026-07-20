"""시점별 티커 별칭을 SEC 원문으로 검증하고 구성 사건으로 번역한다."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

from herd.corporate_continuity_reconciliation import (
    CorporateContinuityError,
    require_terms,
)

VERIFIED_COMPONENT = "VERIFIED_CORPORATE_CONTINUITY_COMPONENT"
RESOLUTION_MODES = {
    "BACKFILLED_ADMISSION_THEN_RENAME",
    "EXISTING_MEMBER_RENAME",
}


def candidate_key(row: dict) -> tuple[str, str, str]:
    return (
        row["candidate_effective_date"],
        row["action"].upper(),
        row["ticker"].upper(),
    )


def parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CorporateContinuityError(f"invalid {field}: {value}") from exc


def verify_alias_ledger(
    aliases: list[dict],
    sec_evidence: dict[str, tuple[bytes, str]],
) -> dict[str, list[dict]]:
    by_entity: dict[str, list[dict]] = defaultdict(list)
    seen_ticker_intervals = set()
    for row in aliases:
        if row.get("verification_status") != "VERIFIED":
            raise CorporateContinuityError("ticker alias row is not verified")
        entity_id = row["entity_id"].strip()
        ticker = row["ticker"].strip().upper()
        start = parse_date(row["valid_from"], "valid_from")
        end = (
            parse_date(row["valid_to"], "valid_to")
            if row.get("valid_to")
            else None
        )
        if end and end < start:
            raise CorporateContinuityError("ticker alias interval is reversed")
        interval_key = (entity_id, ticker, start, end)
        if interval_key in seen_ticker_intervals:
            raise CorporateContinuityError("duplicate ticker alias interval")
        seen_ticker_intervals.add(interval_key)
        source_url = row["sec_source_url"]
        evidence = sec_evidence.get(source_url)
        if not evidence:
            raise CorporateContinuityError(
                f"ticker alias SEC evidence not archived: {source_url}"
            )
        require_terms(
            evidence[0],
            row["required_sec_terms"],
            label="ticker alias SEC",
        )
        by_entity[entity_id].append({
            **row,
            "ticker": ticker,
            "_start": start,
            "_end": end,
            "sec_source_sha256": evidence[1],
        })
    for entity_id, rows in by_entity.items():
        rows.sort(key=lambda row: row["_start"])
        ciks = {row["cik"].zfill(10) for row in rows}
        if len(ciks) != 1:
            raise CorporateContinuityError(
                f"ticker aliases cross CIK boundary: {entity_id}"
            )
        for previous, current in zip(rows, rows[1:]):
            if previous["_end"] is None or previous["_end"] >= current["_start"]:
                raise CorporateContinuityError(
                    f"overlapping ticker aliases: {entity_id}"
                )
            if current.get("predecessor_ticker", "").upper() != previous["ticker"]:
                raise CorporateContinuityError(
                    f"broken ticker predecessor chain: {entity_id}"
                )
            transition = parse_date(
                current["trading_start_date"], "trading_start_date"
            )
            if transition != current["_start"]:
                raise CorporateContinuityError(
                    f"ticker interval does not start on trading date: {entity_id}"
                )
    return by_entity


def reconcile_ticker_aliases(
    reconciliation: list[dict],
    claims: list[dict],
    aliases: list[dict],
    sp_evidence: dict[str, tuple[bytes, str]],
    sec_evidence: dict[str, tuple[bytes, str]],
) -> tuple[list[dict], list[dict], dict]:
    rows_by_key = {candidate_key(row): row for row in reconciliation}
    if len(rows_by_key) != len(reconciliation):
        raise CorporateContinuityError("duplicate reconciliation candidate key")
    aliases_by_entity = verify_alias_ledger(aliases, sec_evidence)
    consumed = {}
    events = []
    for claim in claims:
        mode = claim["resolution_mode"]
        if mode not in RESOLUTION_MODES:
            raise CorporateContinuityError(f"unsupported alias mode: {mode}")
        key = candidate_key(claim)
        candidate = rows_by_key.get(key)
        if not candidate:
            raise CorporateContinuityError(f"alias candidate not found: {key}")
        if candidate["status"] != "UNMATCHED_REQUIRES_TICKER_ALIAS":
            raise CorporateContinuityError(
                f"alias claim targets wrong candidate status: {key}"
            )
        entity_aliases = aliases_by_entity.get(claim["entity_id"], [])
        target_index = next(
            (
                index for index, row in enumerate(entity_aliases)
                if row["ticker"] == claim["ticker"].upper()
            ),
            None,
        )
        if target_index is None:
            raise CorporateContinuityError(f"alias target not found: {key}")
        chain = entity_aliases[: target_index + 1]
        if len(chain) < 2:
            raise CorporateContinuityError("alias resolution requires a transition")
        if mode == "BACKFILLED_ADMISSION_THEN_RENAME":
            sp_item = sp_evidence.get(claim["sp_source_url"])
            if not sp_item:
                raise CorporateContinuityError("alias S&P evidence not archived")
            require_terms(
                sp_item[0], claim["required_sp_terms"], label="ticker alias S&P"
            )
            first = chain[0]
            events.append({
                "event_type": "SUCCESSOR_MEMBERSHIP",
                "candidate_effective_date": claim["candidate_effective_date"],
                "announcement_date": claim.get("announcement_date", ""),
                "corporate_effective_date": "",
                "trading_start_date": claim["index_effective_date"],
                "index_effective_date": claim["index_effective_date"],
                "effective_date": claim["index_effective_date"],
                "event_sequence": 20,
                "action": "ADD",
                "ticker": first["ticker"],
                "old_ticker": "",
                "cik": first["cik"].zfill(10),
                "sp_source_url": claim["sp_source_url"],
                "sp_source_sha256": sp_item[1],
                "sec_source_url": first["sec_source_url"],
                "sec_source_sha256": first["sec_source_sha256"],
            })
        for previous, current in zip(chain, chain[1:]):
            events.append({
                "event_type": "SAME_CIK_RENAME",
                "candidate_effective_date": claim["candidate_effective_date"],
                "announcement_date": current.get("announcement_date", ""),
                "corporate_effective_date": current.get(
                    "corporate_effective_date", ""
                ),
                "trading_start_date": current["trading_start_date"],
                "index_effective_date": current["trading_start_date"],
                "effective_date": current["trading_start_date"],
                "event_sequence": 30,
                "action": "RENAME",
                "ticker": current["ticker"],
                "old_ticker": previous["ticker"],
                "cik": current["cik"].zfill(10),
                "sp_source_url": "",
                "sp_source_sha256": "",
                "sec_source_url": current["sec_source_url"],
                "sec_source_sha256": current["sec_source_sha256"],
            })
        consumed[key] = claim
    updated = [
        {
            **row,
            "status": VERIFIED_COMPONENT,
            "resolved_effective_date": consumed[candidate_key(row)][
                "index_effective_date"
            ],
        }
        if candidate_key(row) in consumed else dict(row)
        for row in reconciliation
    ]
    return updated, events, {
        "verified_alias_entities": len({
            claim["entity_id"] for claim in claims
        }),
        "reclassified_candidate_rows": len(consumed),
        "generated_events": len(events),
        "event_types": dict(Counter(row["event_type"] for row in events)),
        "survivorship_safe": False,
    }

