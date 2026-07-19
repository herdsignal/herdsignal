"""S&P 공식 발표 근거가 있는 구성 변경 이벤트를 검증하고 재생한다."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ALLOWED_ACTIONS = {"ADD", "REMOVE"}
OFFICIAL_HOSTS = {"press.spglobal.com", "www.spglobal.com"}
REQUIRED_FIELDS = {
    "announcement_date",
    "effective_date",
    "action",
    "ticker",
    "company_name",
    "source_url",
    "source_sha256",
}


class OfficialLedgerError(RuntimeError):
    pass


@dataclass(frozen=True)
class ConstituentEvent:
    announcement_date: date
    effective_date: date
    action: str
    ticker: str
    company_name: str
    source_url: str
    source_sha256: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_official_ledger(path: Path) -> list[ConstituentEvent]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not REQUIRED_FIELDS.issubset(reader.fieldnames or []):
            raise OfficialLedgerError(f"missing fields: {sorted(REQUIRED_FIELDS)}")
        events = []
        seen = set()
        for row in reader:
            announcement = date.fromisoformat(row["announcement_date"])
            effective = date.fromisoformat(row["effective_date"])
            action = row["action"].upper()
            ticker = row["ticker"].upper()
            host = urlparse(row["source_url"]).hostname
            if announcement > effective:
                raise OfficialLedgerError("announcement cannot follow effective date")
            if action not in ALLOWED_ACTIONS:
                raise OfficialLedgerError(f"invalid action: {action}")
            if host not in OFFICIAL_HOSTS:
                raise OfficialLedgerError(f"non-official source host: {host}")
            if len(row["source_sha256"]) != 64:
                raise OfficialLedgerError("source_sha256 is required")
            identity = (effective, action, ticker)
            if identity in seen:
                raise OfficialLedgerError(f"duplicate event: {identity}")
            seen.add(identity)
            events.append(
                ConstituentEvent(
                    announcement, effective, action, ticker, row["company_name"].strip(),
                    row["source_url"], row["source_sha256"].lower(),
                )
            )
    return sorted(events, key=lambda event: (event.effective_date, event.action, event.ticker))


def verify_evidence(events: list[ConstituentEvent], evidence_dir: Path) -> None:
    """원문 파일명은 SHA-256이며 내용도 같은 해시여야 한다."""
    for digest in {event.source_sha256 for event in events}:
        matches = list(Path(evidence_dir).glob(f"{digest}.*"))
        if len(matches) != 1 or sha256_file(matches[0]) != digest:
            raise OfficialLedgerError(f"missing or invalid source evidence: {digest}")


def replay_membership(
    baseline: set[str],
    events: list[ConstituentEvent],
    *,
    minimum_size: int = 480,
    maximum_size: int = 510,
) -> tuple[list[dict], dict]:
    current = {ticker.upper() for ticker in baseline}
    if not minimum_size <= len(current) <= maximum_size:
        raise OfficialLedgerError("baseline constituent count is implausible")
    snapshots: list[dict] = []
    by_date: dict[date, list[ConstituentEvent]] = {}
    for event in events:
        by_date.setdefault(event.effective_date, []).append(event)
    for effective, dated_events in sorted(by_date.items()):
        before = set(current)
        # 같은 적용일에는 편출 후 추가한다.
        for event in sorted(dated_events, key=lambda item: item.action, reverse=True):
            if event.action == "REMOVE":
                if event.ticker not in current:
                    raise OfficialLedgerError(
                        f"{effective}: cannot remove absent ticker {event.ticker}"
                    )
                current.remove(event.ticker)
            else:
                if event.ticker in current:
                    raise OfficialLedgerError(
                        f"{effective}: cannot add existing ticker {event.ticker}"
                    )
                current.add(event.ticker)
        if not minimum_size <= len(current) <= maximum_size:
            raise OfficialLedgerError(f"{effective}: constituent count {len(current)} outside gate")
        snapshots.append(
            {
                "effective_date": effective.isoformat(),
                "before_count": len(before),
                "after_count": len(current),
                "added": sorted(current - before),
                "removed": sorted(before - current),
                "tickers": sorted(current),
            }
        )
    return snapshots, {
        "baseline_count": len(baseline),
        "final_count": len(current),
        "event_count": len(events),
        "effective_dates": len(by_date),
        "actions": dict(Counter(event.action for event in events)),
    }


def audit_candidate_coverage(
    official_events: list[ConstituentEvent],
    candidate_events: list[dict],
) -> dict:
    official = {
        (event.effective_date.isoformat(), event.action, event.ticker)
        for event in official_events
    }
    candidates = {
        (row["effective_date"], row["event"], row["ticker"].upper())
        for row in candidate_events
    }
    missing_official_evidence = sorted(candidates - official)
    official_not_discovered = sorted(official - candidates)
    return {
        "candidate_events": len(candidates),
        "official_events": len(official),
        "verified_candidate_events": len(candidates & official),
        "coverage": len(candidates & official) / len(candidates) if candidates else 0.0,
        "missing_official_evidence": missing_official_evidence,
        "official_not_discovered": official_not_discovered,
        "complete": bool(candidates) and candidates <= official,
    }


def write_replay_report(path: Path, snapshots: list[dict], summary: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps({"summary": summary, "snapshots": snapshots}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
