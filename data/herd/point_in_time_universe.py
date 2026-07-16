"""시점별 지수 구성 종목과 비생존 표본 관리."""

from __future__ import annotations

import csv
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = {"ticker", "start_date", "end_date", "sector", "exit_reason", "source"}
EXIT_REASONS = {"active", "removed", "merged", "delisted", "bankrupt"}


def load_universe_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not REQUIRED_FIELDS.issubset(reader.fieldnames or []):
            raise ValueError(f"유니버스 파일 필수 컬럼 누락: {sorted(REQUIRED_FIELDS)}")
        rows = []
        for row in reader:
            if row["exit_reason"] not in EXIT_REASONS:
                raise ValueError(f"알 수 없는 편출 사유: {row['exit_reason']}")
            start = date.fromisoformat(row["start_date"])
            end = date.fromisoformat(row["end_date"]) if row["end_date"] else None
            if end and end < start:
                raise ValueError("end_date는 start_date보다 빠를 수 없습니다.")
            rows.append({**row, "ticker": row["ticker"].upper(), "start_date": start, "end_date": end})
    return rows


def constituents_at(records: list[dict[str, Any]], as_of: date) -> list[str]:
    return sorted({row["ticker"] for row in records
                   if row["start_date"] <= as_of and (row["end_date"] is None or row["end_date"] >= as_of)})


def audit_survivorship_coverage(
    records: list[dict[str, Any]],
    fixed_tickers: list[str],
    minimum_non_survivors: int = 10,
    minimum_historical_coverage: float = 0.5,
) -> dict[str, Any]:
    exits = Counter(row["exit_reason"] for row in records if row["exit_reason"] != "active")
    historical = {row["ticker"] for row in records}
    fixed = set(fixed_tickers)
    non_survivors = historical - fixed
    has_dates = bool(records) and all(row.get("source") and row.get("sector") for row in records)
    historical_coverage = len(historical) / len(fixed) if fixed else 0.0
    ready = (
        has_dates
        and len(non_survivors) >= minimum_non_survivors
        and historical_coverage >= minimum_historical_coverage
    )
    return {
        "fixed_current_tickers": len(fixed), "historical_records": len(records),
        "historical_tickers": len(historical), "non_survivor_tickers": len(non_survivors),
        "historical_coverage": historical_coverage,
        "minimum_non_survivors": minimum_non_survivors,
        "minimum_historical_coverage": minimum_historical_coverage,
        "exit_reason_counts": dict(sorted(exits.items())),
        "point_in_time_ready": ready,
        "status": "POINT_IN_TIME_READY" if ready else "SURVIVORSHIP_BIAS_REMAINS",
    }
