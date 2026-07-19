"""SEC PIT corpus의 접수 시각 연결률과 Company Facts 준비 상태를 감사한다."""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import date
from pathlib import Path

try:
    from herd.sec_point_in_time_fundamentals import (
        build_acceptance_index,
        normalize_companyfacts,
    )
except ModuleNotFoundError:
    from sec_point_in_time_fundamentals import build_acceptance_index, normalize_companyfacts


def audit_corpus(corpus_dir: Path, *, start: date, end: date) -> tuple[list[dict], dict]:
    corpus = Path(corpus_dir)
    raw = corpus / "raw"
    cik_pattern = re.compile(r"CIK(\d{10})-submissions\.json")
    rows = []
    for submissions_path in sorted(raw.glob("CIK*-submissions.json")):
        match = cik_pattern.fullmatch(submissions_path.name)
        if not match:
            continue
        cik = match.group(1)
        payloads = [json.loads(submissions_path.read_text(encoding="utf-8"))]
        payloads.extend(
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(raw.glob(f"CIK{cik}-history-*.json"))
        )
        acceptance = build_acceptance_index(payloads)
        facts_path = raw / f"CIK{cik}-companyfacts.json"
        if not facts_path.exists():
            rows.append({
                "cik": cik, "acceptance_records": len(acceptance), "fact_rows": 0,
                "missing_acceptances": 0, "status": "COMPANYFACTS_UNAVAILABLE",
            })
            continue
        facts = json.loads(facts_path.read_text(encoding="utf-8"))
        normalized, audit = normalize_companyfacts(
            facts, acceptance, strict_acceptance=True,
            filed_from=start, filed_to=end,
        )
        status = (
            "PIT_READY" if audit["point_in_time_ready"] and normalized
            else "MISSING_ACCEPTANCE_LINKS" if audit["missing_acceptances"]
            else "NO_FACT_ROWS_IN_PERIOD"
        )
        rows.append({
            "cik": cik,
            "acceptance_records": len(acceptance),
            "fact_rows": len(normalized),
            "missing_acceptances": audit["missing_acceptances"],
            "status": status,
        })
    statuses = {}
    for row in rows:
        statuses[row["status"]] = statuses.get(row["status"], 0) + 1
    return rows, {
        "ciks": len(rows),
        "statuses": statuses,
        "fact_rows": sum(row["fact_rows"] for row in rows),
        "missing_acceptances": sum(row["missing_acceptances"] for row in rows),
        "pit_ready": bool(rows) and all(row["status"] == "PIT_READY" for row in rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus_dir", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    rows, audit = audit_corpus(args.corpus_dir, start=args.start, end=args.end)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
