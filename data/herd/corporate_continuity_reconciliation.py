"""공식 S&P 구성 지위와 SEC 기업 동일성을 결합해 승계 사건을 검증한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from lxml import html


CONTINUITY_TYPES = {"SAME_CIK_RENAME", "SUCCESSOR_MEMBERSHIP"}
VERIFIED_COMPONENT = "VERIFIED_CORPORATE_CONTINUITY_COMPONENT"


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
        continuity_type = claim["continuity_type"]
        if continuity_type not in CONTINUITY_TYPES:
            raise CorporateContinuityError(
                f"unsupported continuity type: {continuity_type}"
            )
        key = candidate_key(claim)
        candidate = rows_by_key.get(key)
        if not candidate:
            raise CorporateContinuityError(f"candidate not found: {key}")
        if candidate["status"] in {
            "OFFICIAL_TABLE_EXACT",
            "OFFICIAL_PROSE_EXACT",
            "CANDIDATE_DATE_CORRECTED_BY_OFFICIAL_TABLE",
            "CANDIDATE_DATE_CORRECTED_BY_OFFICIAL_PROSE",
            "VERIFIED_IDENTITY_CHANGE_COMPONENT",
        }:
            raise CorporateContinuityError(
                f"claim targets an already resolved candidate: {key}"
            )
        sec_url = claim["filing_url"]
        sec_item = sec_evidence.get(sec_url)
        if not sec_item:
            raise CorporateContinuityError(f"SEC evidence not archived: {sec_url}")
        if (urlparse(sec_url).hostname or "").lower() != "www.sec.gov":
            raise CorporateContinuityError("SEC evidence must use www.sec.gov")
        require_terms(sec_item[0], claim["required_sec_terms"], label="SEC")

        sp_sha = ""
        if continuity_type == "SUCCESSOR_MEMBERSHIP":
            sp_url = claim["sp_source_url"]
            sp_item = sp_evidence.get(sp_url)
            if not sp_item:
                raise CorporateContinuityError(
                    f"S&P evidence not archived: {sp_url}"
                )
            host = (urlparse(sp_url).hostname or "").lower()
            if host != "press.spglobal.com":
                raise CorporateContinuityError(
                    "successor membership requires press.spglobal.com evidence"
                )
            require_terms(sp_item[0], claim["required_sp_terms"], label="S&P")
            sp_sha = sp_item[1]

        consumed[key] = claim
        old_key = (
            claim["candidate_effective_date"],
            "REMOVE",
            claim["old_ticker"].upper(),
        )
        if continuity_type == "SAME_CIK_RENAME" and old_key in rows_by_key:
            consumed[old_key] = claim
        events.append({
            "event_type": continuity_type,
            "effective_date": claim["effective_date"],
            "action": (
                "RENAME" if continuity_type == "SAME_CIK_RENAME" else "ADD"
            ),
            "ticker": claim["ticker"].upper(),
            "old_ticker": claim["old_ticker"].upper(),
            "candidate_effective_date": claim["candidate_effective_date"],
            "cik": claim["cik"].zfill(10),
            "verification_status": "CORPORATE_CONTINUITY_VERIFIED",
            "sp_source_url": claim["sp_source_url"],
            "sp_source_sha256": sp_sha,
            "sec_source_url": sec_url,
            "sec_source_sha256": sec_item[1],
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
            "resolved_effective_date": claim["effective_date"],
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
