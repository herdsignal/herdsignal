"""최신 공개 자료 기준 시점 정합 모집단의 승격 가능성을 감사한다."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json")
PROTOCOL_VERSION = "HERD_SURVIVORSHIP_READINESS_V2"


class SurvivorshipReadinessV2Error(ValueError):
    """모집단 입력이 변조되거나 불완전한 자료가 승격됐을 때 발생한다."""


def _pinned(specification: dict[str, str]) -> Path:
    path = (ROOT / specification["path"]).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise SurvivorshipReadinessV2Error(f"missing input: {specification['path']}")
    if hashlib.sha256(path.read_bytes()).hexdigest() != specification["sha256"]:
        raise SurvivorshipReadinessV2Error(f"hash mismatch: {specification['path']}")
    return path


def _rows(path: Path) -> list[dict[str, str]]:
    if path.suffix == ".gz":
        stream = gzip.open(path, "rt", encoding="utf-8", newline="")
    else:
        stream = path.open("r", encoding="utf-8", newline="")
    with stream:
        return list(csv.DictReader(stream))


def validate_survivorship_readiness_v2(protocol: dict[str, Any]) -> dict[str, Any]:
    if (
        protocol.get("protocol_version") != PROTOCOL_VERSION
        or protocol.get("status") != "LOCKED_PUBLIC_RESEARCH_AUDIT"
    ):
        raise SurvivorshipReadinessV2Error("survivorship protocol is not locked")

    inputs = protocol["inputs"]
    memberships = _rows(_pinned(inputs["community_memberships"]))
    historical_tickers = {row["ticker"] for row in memberships if row.get("ticker")}
    replay = json.loads(_pinned(inputs["official_event_replay"]).read_text())
    event_rows = _rows(_pinned(inputs["event_ledger"]))
    backlog_rows = _rows(_pinned(inputs["event_backlog"]))
    identity = json.loads(_pinned(inputs["identity_report"]).read_text())
    identity_rows = _rows(_pinned(inputs["identity_intervals"]))
    prior = json.loads(_pinned(inputs["prior_delisting_audit"]).read_text())

    price_tickers: set[str] = set()
    price_snapshot_failure_count = 0
    for price_specification in inputs["price_manifests"]:
        manifest = json.loads(_pinned(price_specification).read_text())
        price_snapshot_failure_count += len(manifest.get("failures") or {})
        price_tickers.update(manifest.get("completed_tickers", []))

    replay_audit = replay["audit"]
    unresolved_events = sum(row["event_status"] == "UNRESOLVED" for row in event_rows)
    verified_events = len(event_rows) - unresolved_events
    if (
        verified_events != replay_audit["verified_events"]
        or unresolved_events != replay_audit["blocked_events"]
        or len(backlog_rows) < unresolved_events
    ):
        raise SurvivorshipReadinessV2Error("event replay and ledgers disagree")
    if len(identity_rows) != identity["verified_interval_count"]:
        raise SurvivorshipReadinessV2Error("identity interval count changed")

    historical_price_tickers = historical_tickers & price_tickers
    identity_coverage = identity["verified_canonical_symbol_count"] / len(historical_tickers)
    price_coverage = len(historical_price_tickers) / len(historical_tickers)
    delisted = prior["prices"]
    delisted_coverage = delisted["delisted_available"] / delisted["delisted_requested"]

    checks = {
        "official_membership_history": False,
        "replay_complete": replay_audit["replay_complete"] is True,
        "unresolved_events": unresolved_events <= protocol["gates"]["maximum_unresolved_events"],
        "replay_errors": replay_audit["errors"] <= protocol["gates"]["maximum_replay_errors"],
        "identity_coverage": identity_coverage >= protocol["gates"]["minimum_identity_coverage"],
        "historical_price_coverage": price_coverage >= protocol["gates"]["minimum_historical_price_coverage"],
        "delisted_price_coverage": delisted_coverage >= protocol["gates"]["minimum_delisted_price_coverage"],
        "price_snapshot_failures": price_snapshot_failure_count == 0,
        "price_adjustment_audit": prior["prices"]["adjustment_audited"] is True,
        "split_dividend_audit": prior["corporate_actions"]["split_dividend_audited"] is True,
    }
    failed = [name for name, passed in checks.items() if not passed]
    decision = protocol["decision"]
    if (
        not failed
        or decision.get("status") != "BLOCKED_PUBLIC_DATA_GAPS"
        or decision.get("survivorship_safe") is not False
        or decision.get("promotion_allowed") is not False
        or decision.get("blind_holdout_access") is not False
        or decision.get("operational_action_ratio") != 0.0
    ):
        raise SurvivorshipReadinessV2Error("incomplete universe was promoted")

    return {
        "protocol_version": PROTOCOL_VERSION,
        "historical_tickers": len(historical_tickers),
        "official_events_verified": verified_events,
        "official_events_unresolved": unresolved_events,
        "replay_errors": replay_audit["errors"],
        "identity_tickers": identity["verified_canonical_symbol_count"],
        "identity_coverage": round(identity_coverage, 6),
        "price_tickers": len(historical_price_tickers),
        "historical_price_coverage": round(price_coverage, 6),
        "price_snapshot_failure_count": price_snapshot_failure_count,
        "delisted_requested": delisted["delisted_requested"],
        "delisted_available": delisted["delisted_available"],
        "delisted_price_coverage": round(delisted_coverage, 6),
        "checks": checks,
        "failed_checks": failed,
        "survivorship_safe": False,
        "promotion_allowed": False,
    }


if __name__ == "__main__":
    print(
        json.dumps(
            validate_survivorship_readiness_v2(json.loads(PROTOCOL_PATH.read_text())),
            indent=2,
        )
    )
