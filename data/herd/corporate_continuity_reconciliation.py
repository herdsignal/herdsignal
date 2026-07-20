"""공식 S&P 구성 지위와 SEC 기업 동일성을 결합해 승계 사건을 검증한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from lxml import html


CONTINUITY_TYPES = {
    "SAME_CIK_RENAME",
    "SAME_CIK_MEMBERSHIP_CONTINUITY",
    "SUCCESSOR_MEMBERSHIP",
    "SPINOFF_DUAL_MEMBERSHIP_ADDITION",
    "HISTORICAL_TICKER_ADMISSION_THEN_RENAME",
    "SUCCESSOR_MEMBERSHIP_CONTINUITY",
}
VERIFIED_COMPONENT = "VERIFIED_CORPORATE_CONTINUITY_COMPONENT"
EVIDENCE_BASES = {
    "DIRECT_SP_DJI_EVENT",
    "PRIOR_SP_DJI_MEMBERSHIP_PLUS_SEC_SUCCESSION",
    "PRIOR_SP_DJI_MEMBERSHIP_PLUS_SEC_EXPLICIT_INDEX_ENTRY",
}


class CorporateContinuityError(RuntimeError):
    pass


def normalized_text(content: bytes) -> str:
    try:
        value = html.fromstring(content).text_content()
    except (ValueError, html.etree.ParserError):
        value = content.decode("utf-8", errors="ignore")
    return " ".join(value.split())


def normalized_for_match(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def require_terms(content: bytes, terms: str, *, label: str) -> None:
    text = normalized_for_match(normalized_text(content))
    missing = [
        term for term in terms.split("||")
        if term.strip() and normalized_for_match(term) not in text
    ]
    if missing:
        raise CorporateContinuityError(
            f"{label} evidence is missing required terms: {missing}"
        )


def load_spglobal_corpus(corpus_dir: Path) -> dict[str, tuple[bytes, str]]:
    corpus = Path(corpus_dir)
    with (corpus / "release_index.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    evidence = {}
    for row in rows:
        matches = list(
            (corpus / "evidence").glob(f"{row['source_sha256']}.*")
        )
        if len(matches) != 1:
            raise CorporateContinuityError(
                f"missing S&P evidence: {row['source_url']}"
            )
        content = matches[0].read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != row["source_sha256"]:
            raise CorporateContinuityError(
                f"S&P evidence hash mismatch: {row['source_url']}"
            )
        evidence[row["source_url"]] = (content, digest)
    return evidence


def load_sec_corpus(corpus_dir: Path) -> dict[str, tuple[bytes, str]]:
    corpus = Path(corpus_dir)
    with (corpus / "index.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    evidence = {}
    for row in rows:
        content = (corpus / row["path"]).read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != row["source_sha256"]:
            raise CorporateContinuityError(
                f"SEC evidence hash mismatch: {row['filing_url']}"
            )
        evidence[row["filing_url"]] = (content, digest)
    return evidence


def candidate_key(row: dict) -> tuple[str, str, str]:
    return (
        row["candidate_effective_date"],
        row["action"].upper(),
        row["ticker"].upper(),
    )


def claim_old_tickers(claim: dict) -> list[str]:
    tickers = claim.get("old_tickers", "") or claim["old_ticker"]
    values = [ticker.strip().upper() for ticker in tickers.split("|") if ticker.strip()]
    if not values or len(values) != len(set(values)):
        raise CorporateContinuityError("invalid old_tickers")
    return values


def claim_candidate_keys(claim: dict) -> list[tuple[str, str, str]]:
    encoded = (claim.get("candidate_components") or "").strip()
    if not encoded:
        return [candidate_key(claim)]
    keys = []
    for component in encoded.split("|"):
        parts = [value.strip() for value in component.split(":", 2)]
        if len(parts) != 3:
            raise CorporateContinuityError(
                f"invalid candidate component: {component}"
            )
        try:
            date.fromisoformat(parts[0])
        except ValueError as exc:
            raise CorporateContinuityError(
                f"invalid candidate component date: {component}"
            ) from exc
        if parts[1].upper() not in {"ADD", "REMOVE"} or not parts[2]:
            raise CorporateContinuityError(
                f"invalid candidate component: {component}"
            )
        keys.append((parts[0], parts[1].upper(), parts[2].upper()))
    if len(keys) != len(set(keys)):
        raise CorporateContinuityError("duplicate candidate components")
    return keys


def optional_iso_date(claim: dict, field: str) -> str:
    value = (claim.get(field) or "").strip()
    if value:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise CorporateContinuityError(
                f"invalid {field}: {value}"
            ) from exc
    return value


def timeline_fields(
    claim: dict,
    *,
    index_effective_date: str | None = None,
) -> dict[str, str]:
    index_date = (
        index_effective_date
        or optional_iso_date(claim, "index_effective_date")
        or optional_iso_date(claim, "effective_date")
    )
    if not index_date:
        raise CorporateContinuityError("index_effective_date is required")
    return {
        "announcement_date": optional_iso_date(claim, "announcement_date"),
        "corporate_effective_date": optional_iso_date(
            claim, "corporate_effective_date"
        ),
        "trading_start_date": optional_iso_date(claim, "trading_start_date"),
        "index_effective_date": index_date,
        # Compatibility for downstream readers during schema migration.
        "effective_date": index_date,
    }


def verify_and_reconcile(
    reconciliation: list[dict],
    claims: list[dict],
    sp_evidence: dict[str, tuple[bytes, str]],
    sec_evidence: dict[str, tuple[bytes, str]],
) -> tuple[list[dict], list[dict], dict]:
    rows_by_key = {candidate_key(row): row for row in reconciliation}
    if len(rows_by_key) != len(reconciliation):
        raise CorporateContinuityError("duplicate reconciliation candidate key")
    consumed: dict[tuple[str, str, str], dict] = {}
    events = []
    for claim in claims:
        evidence_basis = (
            claim.get("evidence_basis") or "DIRECT_SP_DJI_EVENT"
        ).upper()
        if evidence_basis not in EVIDENCE_BASES:
            raise CorporateContinuityError(
                f"unsupported evidence basis: {evidence_basis}"
            )
        claim_scope = (claim.get("claim_scope") or "CANDIDATE").upper()
        if claim_scope not in {"CANDIDATE", "STANDALONE"}:
            raise CorporateContinuityError(
                f"unsupported claim scope: {claim_scope}"
            )
        continuity_type = claim["continuity_type"]
        if continuity_type not in CONTINUITY_TYPES:
            raise CorporateContinuityError(
                f"unsupported continuity type: {continuity_type}"
            )
        key = candidate_key(claim)
        component_keys = claim_candidate_keys(claim)
        if claim_scope == "CANDIDATE":
            for component_key in component_keys:
                candidate = rows_by_key.get(component_key)
                if not candidate:
                    raise CorporateContinuityError(
                        f"candidate not found: {component_key}"
                    )
                if candidate["status"] in {
                    "OFFICIAL_TABLE_EXACT",
                    "OFFICIAL_PROSE_EXACT",
                    "CANDIDATE_DATE_CORRECTED_BY_OFFICIAL_TABLE",
                    "CANDIDATE_DATE_CORRECTED_BY_OFFICIAL_PROSE",
                    "CANDIDATE_DATE_CORRECTED_BY_REVIEWED_OFFICIAL_TABLE",
                    "VERIFIED_IDENTITY_CHANGE_COMPONENT",
                }:
                    raise CorporateContinuityError(
                        "claim targets an already resolved candidate: "
                        f"{component_key}"
                    )
        sec_url = claim["filing_url"]
        sec_item = sec_evidence.get(sec_url)
        if not sec_item:
            raise CorporateContinuityError(f"SEC evidence not archived: {sec_url}")
        if (urlparse(sec_url).hostname or "").lower() != "www.sec.gov":
            raise CorporateContinuityError("SEC evidence must use www.sec.gov")
        require_terms(sec_item[0], claim["required_sec_terms"], label="SEC")

        sp_sha = ""
        if continuity_type in {
            "SAME_CIK_MEMBERSHIP_CONTINUITY",
            "SUCCESSOR_MEMBERSHIP",
            "SPINOFF_DUAL_MEMBERSHIP_ADDITION",
            "HISTORICAL_TICKER_ADMISSION_THEN_RENAME",
            "SUCCESSOR_MEMBERSHIP_CONTINUITY",
        }:
            sp_url = claim["sp_source_url"]
            sp_item = sp_evidence.get(sp_url)
            if not sp_item:
                raise CorporateContinuityError(
                    f"S&P evidence not archived: {sp_url}"
                )
            host = (urlparse(sp_url).hostname or "").lower()
            if host not in {"press.spglobal.com", "www.spglobal.com"}:
                raise CorporateContinuityError(
                    "successor membership requires official S&P DJI evidence"
                )
            require_terms(sp_item[0], claim["required_sp_terms"], label="S&P")
            sp_sha = sp_item[1]

        if claim_scope == "CANDIDATE":
            for component_key in component_keys:
                if component_key in consumed:
                    raise CorporateContinuityError(
                        f"candidate consumed by multiple claims: {component_key}"
                    )
                consumed[component_key] = claim
            if continuity_type in {
                "SAME_CIK_RENAME",
                "SAME_CIK_MEMBERSHIP_CONTINUITY",
            }:
                for old_ticker in claim_old_tickers(claim):
                    old_key = (
                        claim["candidate_effective_date"],
                        "REMOVE",
                        old_ticker,
                    )
                    if old_key in rows_by_key:
                        consumed[old_key] = claim
        common_event = {
            "candidate_effective_date": claim["candidate_effective_date"],
            "claim_scope": claim_scope,
            "cik": claim["cik"].zfill(10),
            "verification_status": (
                "CORPORATE_CONTINUITY_INFERRED"
                if evidence_basis
                == "PRIOR_SP_DJI_MEMBERSHIP_PLUS_SEC_SUCCESSION"
                else "CORPORATE_CONTINUITY_VERIFIED"
            ),
            "evidence_basis": evidence_basis,
            "sp_source_url": claim["sp_source_url"],
            "sp_source_sha256": sp_sha,
            "sec_source_url": sec_url,
            "sec_source_sha256": sec_item[1],
        }
        if continuity_type == "HISTORICAL_TICKER_ADMISSION_THEN_RENAME":
            rename_index_date = (
                optional_iso_date(claim, "rename_index_effective_date")
                or optional_iso_date(claim, "rename_effective_date")
            )
            if not rename_index_date:
                raise CorporateContinuityError(
                    "historical admission requires rename_index_effective_date"
                )
            old_tickers = claim_old_tickers(claim)
            if len(old_tickers) != 1:
                raise CorporateContinuityError(
                    "historical admission supports exactly one historical ticker"
                )
            events.extend([
                {
                    **common_event,
                    **timeline_fields(claim),
                    "event_type": "SUCCESSOR_MEMBERSHIP",
                    "action": "ADD",
                    "event_sequence": 20,
                    "ticker": old_tickers[0],
                    "old_ticker": "",
                },
                {
                    **common_event,
                    **timeline_fields(
                        claim,
                        index_effective_date=rename_index_date,
                    ),
                    "corporate_effective_date": (
                        optional_iso_date(claim, "rename_corporate_effective_date")
                        or optional_iso_date(claim, "corporate_effective_date")
                    ),
                    "trading_start_date": (
                        optional_iso_date(claim, "rename_trading_start_date")
                        or optional_iso_date(claim, "trading_start_date")
                    ),
                    "event_type": "SAME_CIK_RENAME",
                    "action": "RENAME",
                    "event_sequence": 30,
                    "ticker": claim["ticker"].upper(),
                    "old_ticker": old_tickers[0],
                },
            ])
            continue
        if continuity_type == "SUCCESSOR_MEMBERSHIP_CONTINUITY":
            events.append({
                **common_event,
                **timeline_fields(claim),
                "event_type": "CORPORATE_SUCCESSION",
                "action": "SUCCESSION",
                "event_sequence": 25,
                "ticker": claim["ticker"].upper(),
                "old_ticker": "|".join(claim_old_tickers(claim)),
            })
            continue
        events.append({
            **common_event,
            **timeline_fields(claim),
            "event_type": continuity_type,
            "action": (
                "RENAME"
                if continuity_type in {
                    "SAME_CIK_RENAME",
                    "SAME_CIK_MEMBERSHIP_CONTINUITY",
                }
                else "ADD"
            ),
            "event_sequence": (
                30
                if continuity_type in {
                    "SAME_CIK_RENAME",
                    "SAME_CIK_MEMBERSHIP_CONTINUITY",
                }
                else 20
            ),
            "ticker": claim["ticker"].upper(),
            "old_ticker": "|".join(claim_old_tickers(claim)),
        })

    updated = []
    for row in reconciliation:
        claim = consumed.get(candidate_key(row))
        if not claim:
            updated.append(dict(row))
            continue
        updated.append({
            **row,
            "status": VERIFIED_COMPONENT,
            "resolved_effective_date": (
                claim.get("index_effective_date")
                or claim["effective_date"]
            ),
            "identity_transition_cik": claim["cik"].zfill(10),
        })
    statuses = Counter(row["status"] for row in updated)
    events.sort(key=lambda row: (row["effective_date"], row["ticker"]))
    return updated, events, {
        "verified_continuity_events": len(events),
        "reclassified_candidate_rows": len(consumed),
        "event_types": dict(Counter(row["event_type"] for row in events)),
        "remaining_non_official_rows": sum(
            row["status"] not in {
                "OFFICIAL_TABLE_EXACT",
                "OFFICIAL_PROSE_EXACT",
                "CANDIDATE_DATE_CORRECTED_BY_OFFICIAL_TABLE",
                "CANDIDATE_DATE_CORRECTED_BY_OFFICIAL_PROSE",
                "CANDIDATE_DATE_CORRECTED_BY_REVIEWED_OFFICIAL_TABLE",
                "VERIFIED_IDENTITY_CHANGE_COMPONENT",
                VERIFIED_COMPONENT,
            }
            for row in updated
        ),
        "statuses": dict(statuses),
        "survivorship_safe": False,
    }


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise CorporateContinuityError("empty output")
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
    parser.add_argument("claims", type=Path)
    parser.add_argument("sp_corpus", type=Path)
    parser.add_argument("sec_corpus", type=Path)
    parser.add_argument("output_reconciliation", type=Path)
    parser.add_argument("output_events", type=Path)
    args = parser.parse_args()
    updated, events, audit = verify_and_reconcile(
        read_csv(args.reconciliation),
        read_csv(args.claims),
        load_spglobal_corpus(args.sp_corpus),
        load_sec_corpus(args.sec_corpus),
    )
    write_csv(args.output_reconciliation, updated)
    write_csv(args.output_events, events)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
