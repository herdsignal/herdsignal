"""엄격 접수시각 자료만으로 기업 상태 방어 지표를 계산할 수 있는지 감사한다."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, time, timezone
from pathlib import Path

from herd.sec_point_in_time_fundamentals import facts_as_of, parse_sec_timestamp
from herd.sec_price_fold_link import _load_cik_facts


CORE_CONCEPTS = {
    "revenue": {
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "SalesRevenueServicesNet",
    },
    "earnings": {"NetIncomeLoss", "ProfitLoss"},
    "operating_cash_flow": {
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    },
    "assets": {"Assets"},
    "liabilities_or_debt": {
        "Liabilities",
        "LiabilitiesAndStockholdersEquity",
        "LongTermDebt",
        "LongTermDebtCurrent",
        "LongTermDebtNoncurrent",
    },
}
MAX_FACT_AGE_DAYS = 550


def _read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _group_evidence(rows: list[dict], as_of: datetime) -> dict[str, dict]:
    evidence = {}
    for group, aliases in CORE_CONCEPTS.items():
        matches = [row for row in rows if row["concept"] in aliases]
        latest = max(
            (parse_sec_timestamp(row["accepted_at"]) for row in matches),
            default=None,
        )
        age = (as_of - latest).days if latest else None
        evidence[group] = {
            "concepts": sorted({row["concept"] for row in matches}),
            "latest_accepted_at": latest.isoformat() if latest else "",
            "age_days": age,
            "ready": latest is not None and 0 <= age <= MAX_FACT_AGE_DAYS,
        }
    return evidence


def audit_feature_readiness(
    link_rows: list[dict],
    corpora: list[Path],
) -> tuple[list[dict], dict]:
    """비정상 corpus 행도 검증된 관측만 사용해 guard 가능 여부를 분리한다."""
    candidates = [
        row
        for row in link_rows
        if row["asset_type"] == "EQUITY"
        and row["cik"]
        and row["status"] != "PIT_FACTS_READY"
    ]
    cache: dict[str, tuple[list[dict], str]] = {}
    output = []
    for row in candidates:
        cik = row["cik"]
        if cik not in cache:
            cache[cik] = _load_cik_facts(
                corpora,
                cik,
                filed_from=date(1900, 1, 1),
                filed_to=max(date.fromisoformat(item["as_of"]) for item in candidates),
            )
        facts, corpus_status = cache[cik]
        boundary = datetime.combine(
            date.fromisoformat(row["as_of"]),
            time.min,
            tzinfo=timezone.utc,
        )
        available = facts_as_of(facts, boundary)
        evidence = _group_evidence(available, boundary)
        missing = sorted(
            group for group, item in evidence.items() if not item["ready"]
        )
        output.append({
            "ticker": row["ticker"],
            "cik": cik,
            "fold_id": row["fold_id"],
            "as_of": row["as_of"],
            "source_status": corpus_status,
            "strict_fact_rows": len(available),
            "ready_groups": len(CORE_CONCEPTS) - len(missing),
            "required_groups": len(CORE_CONCEPTS),
            "missing_or_stale_groups": "|".join(missing),
            "feature_status": (
                "BUSINESS_GUARD_READY_WITH_DISCLOSED_EXCLUSIONS"
                if not missing
                else "BUSINESS_GUARD_BLOCKED"
            ),
            "evidence_json": json.dumps(
                evidence, ensure_ascii=False, separators=(",", ":")
            ),
        })
    ready = [
        row for row in output
        if row["feature_status"]
        == "BUSINESS_GUARD_READY_WITH_DISCLOSED_EXCLUSIONS"
    ]
    return output, {
        "format_version": "herd-sec-pit-feature-readiness-v1",
        "max_fact_age_days": MAX_FACT_AGE_DAYS,
        "core_concept_groups": {
            group: sorted(aliases) for group, aliases in CORE_CONCEPTS.items()
        },
        "audited_rows": len(output),
        "guard_ready_rows": len(ready),
        "guard_blocked_rows": len(output) - len(ready),
        "strict_corpus_ready": not output,
        "guard_research_ready": bool(output) and len(ready) == len(output),
        "interpretation": (
            "guard_research_ready permits only the business deterioration veto. "
            "It does not repair or include observations without SEC acceptance times."
        ),
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("links", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("output_audit", type=Path)
    parser.add_argument(
        "--corpus", type=Path, action="append", required=True
    )
    args = parser.parse_args()
    rows, audit = audit_feature_readiness(_read_csv(args.links), args.corpus)
    write_csv(args.output_csv, rows)
    args.output_audit.parent.mkdir(parents=True, exist_ok=True)
    args.output_audit.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
