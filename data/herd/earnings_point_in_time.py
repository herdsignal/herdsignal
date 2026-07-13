"""발표일이 검증된 EPS 레코드만 사용하는 point-in-time 보정."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd

from config.settings import EPS_SURPRISE_MULTIPLIERS

TRUSTED_DATE_SOURCES = {"sec_filing", "company_ir", "exchange_release", "licensed_earnings_feed"}


def validate_earnings_record(record: dict[str, Any]) -> tuple[bool, str]:
    required = ("announcement_date", "actual", "estimate", "date_source")
    if any(record.get(key) is None for key in required):
        return False, "missing_required_field"
    if record["date_source"] not in TRUSTED_DATE_SOURCES:
        return False, "untrusted_announcement_date"
    try:
        pd.Timestamp(record["announcement_date"])
        float(record["actual"])
        estimate = float(record["estimate"])
    except (TypeError, ValueError):
        return False, "invalid_value"
    if estimate == 0:
        return False, "zero_estimate"
    return True, "accepted"


def _streak_multiplier(surprises: list[float]) -> float:
    if len(surprises) < 2 or surprises[0] == 0:
        return EPS_SURPRISE_MULTIPLIERS["neutral"]
    direction = 1 if surprises[0] > 0 else -1
    streak = 0
    for value in surprises[:4]:
        if value * direction > 0: streak += 1
        else: break
    prefix = "beat" if direction > 0 else "miss"
    return EPS_SURPRISE_MULTIPLIERS.get(f"{prefix}_{streak}", EPS_SURPRISE_MULTIPLIERS["neutral"])


def build_eps_multiplier_series(records: list[dict[str, Any]], index: pd.DatetimeIndex) -> tuple[pd.Series, dict[str, Any]]:
    accepted, rejected = [], []
    for record in records:
        valid, reason = validate_earnings_record(record)
        (accepted if valid else rejected).append(record if valid else {"record": record, "reason": reason})
    accepted.sort(key=lambda row: pd.Timestamp(row["announcement_date"]))
    values = []
    for timestamp in index:
        known = [row for row in accepted if pd.Timestamp(row["announcement_date"]) <= timestamp]
        surprises = [(float(row["actual"]) / float(row["estimate"]) - 1) * 100 for row in reversed(known[-4:])]
        values.append(_streak_multiplier(surprises))
    status = "ACTIVE" if accepted else "EXCLUDED_NO_TRUSTED_ANNOUNCEMENT_DATES"
    return pd.Series(values, index=index, dtype=float), {
        "status": status, "accepted_records": len(accepted), "rejected_records": len(rejected),
        "rejection_reasons": sorted({row["reason"] for row in rejected}),
    }
