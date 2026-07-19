"""SEC Company Facts를 접수 시각 기준 point-in-time 레코드로 정규화한다."""

from __future__ import annotations

import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path


class SecFundamentalsError(RuntimeError):
    pass


def parse_sec_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise SecFundamentalsError("SEC acceptance timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def build_acceptance_index(submissions_payloads: list[dict]) -> dict[str, str]:
    """기본 submissions와 과거 filings 조각을 같은 columnar schema로 읽는다."""
    index: dict[str, str] = {}
    for payload in submissions_payloads:
        recent = payload.get("filings", {}).get("recent", payload)
        accessions = recent.get("accessionNumber", [])
        accepted = recent.get("acceptanceDateTime", [])
        if len(accessions) != len(accepted):
            raise SecFundamentalsError("submissions accession/acceptance columns differ")
        for accession, timestamp in zip(accessions, accepted, strict=True):
            if not accession or not timestamp:
                continue
            normalized = parse_sec_timestamp(timestamp).isoformat()
            if accession in index and index[accession] != normalized:
                raise SecFundamentalsError(f"conflicting acceptance time: {accession}")
            index[accession] = normalized
    return index


def normalize_companyfacts(
    payload: dict,
    acceptance_index: dict[str, str],
    *,
    strict_acceptance: bool = True,
    filed_from: date | None = None,
    filed_to: date | None = None,
) -> tuple[list[dict], dict]:
    cik = f"{int(payload['cik']):010d}"
    rows = []
    missing_accessions = set()
    for taxonomy, concepts in payload.get("facts", {}).items():
        for concept, detail in concepts.items():
            for unit, observations in detail.get("units", {}).items():
                for observation in observations:
                    filed_value = observation.get("filed", "")
                    if filed_from and (
                        not filed_value or date.fromisoformat(filed_value) < filed_from
                    ):
                        continue
                    if filed_to and (
                        not filed_value or date.fromisoformat(filed_value) > filed_to
                    ):
                        continue
                    accession = observation.get("accn", "")
                    accepted_at = acceptance_index.get(accession, "")
                    if not accepted_at:
                        missing_accessions.add(accession)
                        if strict_acceptance:
                            continue
                    rows.append(
                        {
                            "cik": cik,
                            "entity_name": payload.get("entityName", ""),
                            "taxonomy": taxonomy,
                            "concept": concept,
                            "label": detail.get("label", ""),
                            "unit": unit,
                            "period_start": observation.get("start", ""),
                            "period_end": observation.get("end", ""),
                            "value_json": json.dumps(
                                observation.get("val"), ensure_ascii=False, separators=(",", ":")
                            ),
                            "accession_number": accession,
                            "form": observation.get("form", ""),
                            "filed_date": observation.get("filed", ""),
                            "accepted_at": accepted_at,
                            "fiscal_year": observation.get("fy", ""),
                            "fiscal_period": observation.get("fp", ""),
                            "frame": observation.get("frame", ""),
                            "availability": (
                                "ACCEPTANCE_TIME_VERIFIED"
                                if accepted_at
                                else "MISSING_ACCEPTANCE_TIME"
                            ),
                        }
                    )
    rows.sort(
        key=lambda row: (
            row["taxonomy"], row["concept"], row["unit"], row["period_end"],
            row["accepted_at"], row["accession_number"],
        )
    )
    missing_count = len({item for item in missing_accessions if item})
    return rows, {
        "cik": cik,
        "rows": len(rows),
        "strict_acceptance": strict_acceptance,
        "missing_acceptances": missing_count,
        "point_in_time_ready": strict_acceptance and missing_count == 0,
    }


def facts_as_of(
    rows: list[dict],
    as_of: datetime,
    *,
    taxonomy: str | None = None,
    concept: str | None = None,
) -> list[dict]:
    if as_of.tzinfo is None:
        raise SecFundamentalsError("as_of must include a timezone")
    boundary = as_of.astimezone(timezone.utc)
    eligible = []
    for row in rows:
        if row["availability"] != "ACCEPTANCE_TIME_VERIFIED":
            continue
        if taxonomy and row["taxonomy"] != taxonomy:
            continue
        if concept and row["concept"] != concept:
            continue
        if parse_sec_timestamp(row["accepted_at"]) <= boundary:
            eligible.append(row)
    return eligible


def write_facts(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise SecFundamentalsError("no point-in-time facts to write")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
