"""S&P 편출 이벤트와 SEC Form 25/25-NSE 접수 증거를 연결한다."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

try:
    from herd.sec_company_cik_linker import iter_master_rows
except ModuleNotFoundError:
    from sec_company_cik_linker import iter_master_rows

DELISTING_FORMS = {"25", "25-NSE"}


class SecDelistingEvidenceError(RuntimeError):
    pass


def find_form25_candidates(
    linked_events: list[dict],
    master_snapshot: Path,
    *,
    lookback_days: int = 30,
    forward_days: int = 180,
) -> tuple[list[dict], dict]:
    eligible = [
        row for row in linked_events
        if row["action"] == "REMOVE"
        and row["cik_link_status"] == "UNIQUE_CIK_NAME_CANDIDATE"
        and row["cik"]
    ]
    by_cik = defaultdict(list)
    for event in eligible:
        by_cik[event["cik"]].append(event)
    filings = defaultdict(list)
    for path in sorted((Path(master_snapshot) / "raw").glob("*-master.idx")):
        for cik, company, form, filed, filename in iter_master_rows(path):
            normalized_cik = f"{int(cik):010d}"
            if normalized_cik in by_cik and form in DELISTING_FORMS:
                filings[normalized_cik].append({
                    "sec_company_name": company,
                    "form": form,
                    "filed_date": filed,
                    "filename": filename,
                })
    results = []
    status_counts = defaultdict(int)
    for event in eligible:
        effective = date.fromisoformat(event["effective_date"])
        candidates = [
            filing for filing in filings[event["cik"]]
            if effective - timedelta(days=lookback_days)
            <= date.fromisoformat(filing["filed_date"])
            <= effective + timedelta(days=forward_days)
        ]
        status = (
            "NO_FORM25_IN_WINDOW" if not candidates
            else "UNIQUE_FORM25_CANDIDATE" if len(candidates) == 1
            else "MULTIPLE_FORM25_CANDIDATES"
        )
        status_counts[status] += 1
        if not candidates:
            results.append({
                "effective_date": event["effective_date"],
                "ticker": event["ticker"],
                "company_name": event["company_name"],
                "cik": event["cik"],
                "status": status,
                "form": "", "filed_date": "", "filing_url": "",
            })
            continue
        for filing in candidates:
            results.append({
                "effective_date": event["effective_date"],
                "ticker": event["ticker"],
                "company_name": event["company_name"],
                "cik": event["cik"],
                "status": status,
                "form": filing["form"],
                "filed_date": filing["filed_date"],
                "filing_url": f"https://www.sec.gov/Archives/{filing['filename']}",
            })
    return results, {
        "eligible_removal_events": len(eligible),
        "statuses": dict(status_counts),
        "candidate_rows": sum(bool(row["filing_url"]) for row in results),
        "complete": False,
        "reason": "Form 25 document contents still require security-class review",
    }


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise SecDelistingEvidenceError("no eligible removal events")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("linked_events", type=Path)
    parser.add_argument("master_snapshot", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows, audit = find_form25_candidates(
        read_csv(args.linked_events), args.master_snapshot
    )
    write_csv(args.output, rows)
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
