"""S&P 편출 사건 주변의 SEC 합병·인수 공시 후보를 수집·분류한다."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

try:
    from herd.sec_company_cik_linker import iter_master_rows
except ModuleNotFoundError:
    from sec_company_cik_linker import iter_master_rows

MERGER_FORMS = {"8-K", "8-K/A", "S-4", "S-4/A", "DEFM14A"}
COMPLETION = re.compile(
    r"(consummated|completed|completion|closing)\b.{0,120}\b(merger|acquisition)|"
    r"(merger|acquisition)\b.{0,120}\b(consummated|completed|completion|closing)",
    re.IGNORECASE | re.DOTALL,
)
AGREEMENT = re.compile(r"(agreement and plan of merger|merger agreement)", re.IGNORECASE)
DELISTING = re.compile(
    r"(delist|removal from listing|cease[sd]? to be traded|form 25)", re.IGNORECASE
)


def filing_window(form: str, effective: date) -> tuple[date, date]:
    if form in {"8-K", "8-K/A"}:
        return effective - timedelta(days=45), effective + timedelta(days=60)
    return effective - timedelta(days=400), effective + timedelta(days=30)


def find_merger_candidates(events: list[dict], master_snapshot: Path) -> tuple[list[dict], dict]:
    eligible = [
        row for row in events
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
            normalized = f"{int(cik):010d}"
            if normalized in by_cik and form in MERGER_FORMS:
                filings[normalized].append((form, filed, filename))
    rows = []
    events_with_candidates = set()
    for event in eligible:
        effective = date.fromisoformat(event["effective_date"])
        for form, filed, filename in filings[event["cik"]]:
            start, end = filing_window(form, effective)
            if start <= date.fromisoformat(filed) <= end:
                events_with_candidates.add((event["effective_date"], event["ticker"]))
                rows.append({
                    "effective_date": event["effective_date"],
                    "ticker": event["ticker"],
                    "company_name": event["company_name"],
                    "cik": event["cik"],
                    "form": form,
                    "filed_date": filed,
                    "filing_url": f"https://www.sec.gov/Archives/{filename}",
                    "review_status": "REQUIRES_DOCUMENT_REVIEW",
                })
    return rows, {
        "eligible_removal_events": len(eligible),
        "events_with_candidates": len(events_with_candidates),
        "candidate_documents": len(rows),
        "complete": False,
    }


def classify_merger_document(content: bytes) -> dict:
    text = content.decode("latin-1", errors="replace")
    completed = bool(COMPLETION.search(text))
    agreement = bool(AGREEMENT.search(text))
    delisting = bool(DELISTING.search(text))
    if completed and delisting:
        status = "MERGER_COMPLETION_AND_DELISTING_EVIDENCE"
    elif completed:
        status = "MERGER_COMPLETION_EVIDENCE"
    elif agreement:
        status = "MERGER_AGREEMENT_EVIDENCE"
    else:
        status = "NO_STRONG_MERGER_EVIDENCE"
    return {
        "classification_status": status,
        "completion_marker": completed,
        "agreement_marker": agreement,
        "delisting_marker": delisting,
        "requires_review": True,
    }


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise RuntimeError("no merger filing candidates")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def classify_merger_corpus(
    candidate_rows: list[dict], corpus_dir: Path
) -> tuple[list[dict], dict]:
    corpus = Path(corpus_dir)
    index = {
        row["filing_url"]: row
        for row in read_csv(corpus / "index.csv")
    }
    rows = []
    statuses = defaultdict(int)
    events_with_completion = set()
    events_with_agreement = set()
    for candidate in candidate_rows:
        source = index.get(candidate["filing_url"])
        if not source:
            raise RuntimeError(f"missing corpus document: {candidate['filing_url']}")
        result = classify_merger_document((corpus / source["path"]).read_bytes())
        status = result["classification_status"]
        statuses[status] += 1
        event_key = (candidate["effective_date"], candidate["ticker"])
        if status.startswith("MERGER_COMPLETION"):
            events_with_completion.add(event_key)
        elif status == "MERGER_AGREEMENT_EVIDENCE":
            events_with_agreement.add(event_key)
        rows.append({
            **candidate,
            "source_sha256": source["source_sha256"],
            **result,
        })
    return rows, {
        "documents": len(rows),
        "statuses": dict(statuses),
        "events_with_completion_evidence": len(events_with_completion),
        "events_with_agreement_only": len(events_with_agreement - events_with_completion),
        "complete": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    find = sub.add_parser("find")
    find.add_argument("events", type=Path)
    find.add_argument("master_snapshot", type=Path)
    find.add_argument("output", type=Path)
    classify = sub.add_parser("classify")
    classify.add_argument("candidates", type=Path)
    classify.add_argument("corpus_dir", type=Path)
    classify.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.command == "find":
        rows, audit = find_merger_candidates(read_csv(args.events), args.master_snapshot)
    else:
        rows, audit = classify_merger_corpus(
            read_csv(args.candidates), args.corpus_dir
        )
    write_csv(args.output, rows)
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
