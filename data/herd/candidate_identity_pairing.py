"""미해결 REMOVE/ADD 후보에서 구성 연속성 검토용 ticker 쌍을 만든다."""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import date
from pathlib import Path

RESOLVED = {
    "OFFICIAL_TABLE_EXACT",
    "OFFICIAL_PROSE_EXACT",
    "CANDIDATE_DATE_CORRECTED_BY_OFFICIAL_TABLE",
    "CANDIDATE_DATE_CORRECTED_BY_OFFICIAL_PROSE",
    "CANDIDATE_DATE_CORRECTED_BY_REVIEWED_OFFICIAL_TABLE",
}


class IdentityPairingError(RuntimeError):
    pass


def canonical_ticker(value: str) -> str:
    ticker = re.sub(r"\s*\(PREVIOUSLY\s+[^)]+\)\s*", "", value, flags=re.IGNORECASE)
    return re.sub(r"[^A-Z0-9]", "", ticker.upper())


def pair_identity_candidates(
    reconciliation: list[dict],
    current_ticker_cik: list[dict],
    *,
    maximum_gap_days: int = 4,
) -> tuple[list[dict], dict]:
    unresolved = [row for row in reconciliation if row["status"] not in RESOLVED]
    adds = [row for row in unresolved if row["action"] == "ADD"]
    removes = [row for row in unresolved if row["action"] == "REMOVE"]
    cik_by_ticker = {
        row["ticker"].upper(): row["cik"]
        for row in current_ticker_cik
        if row.get("ticker") and row.get("cik")
    }
    ciks_by_canonical = {}
    for ticker, cik in cik_by_ticker.items():
        ciks_by_canonical.setdefault(canonical_ticker(ticker), set()).add(cik)
    rows = []
    for addition in adds:
        add_date = date.fromisoformat(addition["candidate_effective_date"])
        new_ticker = addition["ticker"].upper()
        for removal in removes:
            remove_date = date.fromisoformat(removal["candidate_effective_date"])
            gap = abs((add_date - remove_date).days)
            if gap > maximum_gap_days:
                continue
            old_ticker = removal["ticker"].upper()
            if old_ticker == new_ticker:
                continue
            same_symbol = canonical_ticker(new_ticker) == canonical_ticker(old_ticker)
            new_cik = cik_by_ticker.get(new_ticker, "")
            if not new_cik:
                canonical_ciks = ciks_by_canonical.get(canonical_ticker(new_ticker), set())
                if len(canonical_ciks) == 1:
                    new_cik = next(iter(canonical_ciks))
            if same_symbol:
                status = "SYMBOL_FORMAT_CONTINUITY_CANDIDATE"
            elif new_cik:
                status = "REQUIRES_SEC_TRADING_SYMBOL_EVIDENCE"
            else:
                continue
            rows.append({
                "old_candidate_date": removal["candidate_effective_date"],
                "new_candidate_date": addition["candidate_effective_date"],
                "old_ticker": old_ticker,
                "new_ticker": new_ticker,
                "candidate_gap_days": gap,
                "candidate_cik": new_cik,
                "pairing_status": status,
                "evidence_role": "IDENTITY_CONTINUITY_CANDIDATE_ONLY",
            })
    rows.sort(key=lambda row: (
        row["new_candidate_date"], row["new_ticker"], row["old_ticker"]
    ))
    return rows, {
        "unresolved_events": len(unresolved),
        "pair_candidates": len(rows),
        "format_only_candidates": sum(
            row["pairing_status"] == "SYMBOL_FORMAT_CONTINUITY_CANDIDATE"
            for row in rows
        ),
        "sec_evidence_candidates": sum(
            row["pairing_status"] == "REQUIRES_SEC_TRADING_SYMBOL_EVIDENCE"
            for row in rows
        ),
        "verified_identity_changes": 0,
        "membership_events_reclassified": 0,
    }


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise IdentityPairingError("no identity pair candidates")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reconciliation", type=Path)
    parser.add_argument("current_ticker_cik", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows, audit = pair_identity_candidates(
        read_csv(args.reconciliation), read_csv(args.current_ticker_cik)
    )
    write_csv(args.output, rows)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
