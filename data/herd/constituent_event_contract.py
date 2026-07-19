"""S&P 구성 사건의 증거와 적용 시점을 보존하는 데이터 계약."""

from __future__ import annotations

import re
from datetime import date
from urllib.parse import urlparse

ACTION_VALUES = {"ADD", "REMOVE"}
TIMING_VALUES = {"PRIOR_TO_OPEN", "AFTER_CLOSE", "UNSPECIFIED"}
EVIDENCE_LEVELS = {
    "OFFICIAL_TABLE": 3,
    "OFFICIAL_PROSE": 2,
    "OFFICIAL_CORRECTION": 4,
}
SHA256 = re.compile(r"[0-9a-f]{64}")

PRIOR_TO_OPEN = re.compile(
    r"(?:effective\s+)?prior to (?:the\s+)?open(?:ing)?|"
    r"before (?:the\s+)?market opens|at the open",
    re.IGNORECASE,
)
AFTER_CLOSE = re.compile(
    r"(?:effective\s+)?after (?:the\s+)?close(?: of trading)?|"
    r"following the close(?: of trading)?|at the close",
    re.IGNORECASE,
)


class ConstituentEventContractError(ValueError):
    pass


def classify_effective_timing(context: str) -> str:
    prior = bool(PRIOR_TO_OPEN.search(context))
    after = bool(AFTER_CLOSE.search(context))
    if prior and after:
        raise ConstituentEventContractError("conflicting effective timing phrases")
    if prior:
        return "PRIOR_TO_OPEN"
    if after:
        return "AFTER_CLOSE"
    return "UNSPECIFIED"


def membership_session_date(
    stated_effective_date: str,
    effective_timing: str,
    trading_sessions: list[str],
) -> str | None:
    if effective_timing not in TIMING_VALUES:
        raise ConstituentEventContractError(
            f"unsupported effective timing: {effective_timing}"
        )
    if effective_timing == "UNSPECIFIED":
        return None
    stated = date.fromisoformat(stated_effective_date)
    sessions = sorted({date.fromisoformat(value) for value in trading_sessions})
    eligible = (
        [session for session in sessions if session >= stated]
        if effective_timing == "PRIOR_TO_OPEN"
        else [session for session in sessions if session > stated]
    )
    return eligible[0].isoformat() if eligible else None


def validate_official_event(event: dict) -> None:
    required = {
        "announcement_date",
        "stated_effective_date",
        "effective_timing",
        "action",
        "ticker",
        "source_url",
        "source_sha256",
        "evidence_type",
    }
    missing = sorted(required - event.keys())
    if missing:
        raise ConstituentEventContractError(
            f"missing official event fields: {', '.join(missing)}"
        )
    announcement = date.fromisoformat(event["announcement_date"])
    stated = date.fromisoformat(event["stated_effective_date"])
    if announcement > stated:
        raise ConstituentEventContractError(
            "announcement date is after stated effective date"
        )
    if event["action"] not in ACTION_VALUES:
        raise ConstituentEventContractError(f"unsupported action: {event['action']}")
    if event["effective_timing"] not in TIMING_VALUES:
        raise ConstituentEventContractError(
            f"unsupported effective timing: {event['effective_timing']}"
        )
    if event["evidence_type"] not in EVIDENCE_LEVELS:
        raise ConstituentEventContractError(
            f"unsupported evidence type: {event['evidence_type']}"
        )
    host = (urlparse(event["source_url"]).hostname or "").lower()
    if host != "spglobal.com" and not host.endswith(".spglobal.com"):
        raise ConstituentEventContractError(f"non-official source host: {host}")
    if not SHA256.fullmatch(event["source_sha256"]):
        raise ConstituentEventContractError("invalid source sha256")
    if not event["ticker"].strip():
        raise ConstituentEventContractError("empty ticker")


def build_official_event(
    *,
    announcement_date: str,
    stated_effective_date: str,
    timing_context: str,
    action: str,
    ticker: str,
    source_url: str,
    source_sha256: str,
    evidence_type: str,
    trading_sessions: list[str],
) -> dict:
    timing = classify_effective_timing(timing_context)
    event = {
        "announcement_date": announcement_date,
        "stated_effective_date": stated_effective_date,
        "effective_timing": timing,
        "membership_session_date": membership_session_date(
            stated_effective_date, timing, trading_sessions
        ),
        "action": action.upper(),
        "ticker": ticker.upper().strip(),
        "source_url": source_url,
        "source_sha256": source_sha256.lower(),
        "evidence_type": evidence_type,
        "timing_evidence_context": " ".join(timing_context.split()),
    }
    validate_official_event(event)
    return event
