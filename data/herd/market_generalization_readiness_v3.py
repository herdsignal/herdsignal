"""공개 데이터만으로 가능한 개인 진단과 시장 일반화 범위를 분리한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from herd.survivorship_readiness_v2 import (
    validate_survivorship_readiness_v2,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
REPORT_PATH = ROOT / "data/reports/market_generalization_readiness_v3.json"
VERSION = "HERD_MARKET_GENERALIZATION_READINESS_V3"


class MarketGeneralizationReadinessError(ValueError):
    pass


def _load_protocol(specification: dict[str, str]) -> dict[str, Any]:
    path = (ROOT / specification["path"]).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise MarketGeneralizationReadinessError("survivorship input missing")
    if hashlib.sha256(path.read_bytes()).hexdigest() != specification["sha256"]:
        raise MarketGeneralizationReadinessError("survivorship input changed")
    return json.loads(path.read_text())


def build_report(output_path: Path = REPORT_PATH) -> dict[str, Any]:
    contract = json.loads(CONTRACT_PATH.read_text())
    if (
        contract.get("gate_version") != VERSION
        or contract.get("status") != "LOCKED_PUBLIC_DATA_SCOPE"
    ):
        raise MarketGeneralizationReadinessError(
            "market generalization gate is not locked"
        )
    audit = validate_survivorship_readiness_v2(
        _load_protocol(contract["input"])
    )
    if audit["survivorship_safe"]:
        raise MarketGeneralizationReadinessError(
            "market lane requires a separately sealed promotion decision"
        )
    report = {
        "report_version": VERSION,
        "status": "PERSONAL_DIAGNOSTIC_ALLOWED_MARKET_GENERALIZATION_BLOCKED",
        "period": {"start": "2016-07-18", "end": "2026-07-17"},
        "coverage": {
            "historical_tickers": audit["historical_tickers"],
            "identity_tickers": audit["identity_tickers"],
            "identity_fraction": audit["identity_coverage"],
            "price_tickers": audit["price_tickers"],
            "historical_price_fraction":
                audit["historical_price_coverage"],
            "delisted_requested": audit["delisted_requested"],
            "delisted_available": audit["delisted_available"],
            "delisted_price_fraction":
                audit["delisted_price_coverage"],
        },
        "event_replay": {
            "verified": audit["official_events_verified"],
            "unresolved": audit["official_events_unresolved"],
            "errors": audit["replay_errors"],
            "complete": audit["checks"]["replay_complete"],
        },
        "failed_checks": audit["failed_checks"],
        "allowed_claim": "CURRENT_CONSTITUENT_PERSONAL_DIAGNOSTIC",
        "blocked_claim": "HISTORICAL_SP500_MARKET_GENERALIZATION",
        "survivorship_safe": False,
        "promotion_allowed": False,
        "blind_holdout_access": False,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(build_report(), indent=2))
