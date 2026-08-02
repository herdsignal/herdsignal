"""Collect SEC earnings events for the former-constituent expansion cohort."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

from herd.sec_earnings_event_ledger_v1 import collect_events
from herd.sec_master_index import resolve_user_agent
from herd.ticker_disjoint_sec_earnings_census_v1 import (
    load_cik_universe,
    materialize_catalog,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
DEFAULT_LEDGER = ROOT / "data/runtime/action-research/ticker-disjoint-sec-earnings-v2.jsonl"
DEFAULT_CATALOG = ROOT / "data/reports/ticker_disjoint_sec_earnings_census_v2.csv"
DEFAULT_REPORT = ROOT / "data/reports/ticker_disjoint_sec_earnings_census_v2.json"


class TickerDisjointSecCensusV2Error(RuntimeError):
    """Raised when the expansion input or SEC event corpus is invalid."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if (
        contract.get("contract_version") != "TICKER_DISJOINT_SEC_EARNINGS_CENSUS_V2"
        or contract.get("status") != "LOCKED_BEFORE_REACTION_OUTCOMES"
        or contract.get("operational_action_ratio") != 0.0
    ):
        raise TickerDisjointSecCensusV2Error("SEC census V2 contract is not locked")
    for key in ("universe", "input_lock"):
        item = contract[key]
        source = (ROOT / item["path"]).resolve()
        if not source.is_relative_to(ROOT) or not source.is_file() or _sha256(source) != item["sha256"]:
            raise TickerDisjointSecCensusV2Error(f"locked {key} changed")
    return contract


def run(
    *,
    collect: bool,
    ledger_path: Path = DEFAULT_LEDGER,
    catalog_path: Path = DEFAULT_CATALOG,
    report_path: Path = DEFAULT_REPORT,
    env_file: Path = ROOT / ".env",
) -> dict[str, Any]:
    contract = load_contract()
    universe = load_cik_universe(contract)
    collection = None
    if collect:
        collection = collect_events(
            universe,
            ledger_path,
            user_agent=resolve_user_agent(env_file),
            accepted_on_or_after=date.fromisoformat(contract["accepted_on_or_after"]),
            include_historical_files=True,
        )
    catalog = materialize_catalog(ledger_path, universe, catalog_path)
    covered = int(catalog["ticker"].nunique()) if len(catalog) else 0
    report = {
        "report_version": "TICKER_DISJOINT_SEC_EARNINGS_CENSUS_V2",
        "status": "SEC_HISTORY_READY" if covered == len(universe) else "SEC_HISTORY_PARTIAL",
        "universe_tickers": len(universe),
        "covered_tickers": covered,
        "events": len(catalog),
        "first_acceptance": catalog["accepted_at"].min() if len(catalog) else None,
        "last_acceptance": catalog["accepted_at"].max() if len(catalog) else None,
        "catalog_path": str(catalog_path.relative_to(ROOT)),
        "catalog_sha256": _sha256(catalog_path),
        "ledger_sha256": _sha256(ledger_path) if ledger_path.is_file() else None,
        "collection": collection,
        "future_price_outcomes_read": False,
        "survivorship_safe": False,
        "blind_holdout": False,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collect", action="store_true")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    args = parser.parse_args()
    print(json.dumps(run(collect=args.collect, ledger_path=args.ledger), ensure_ascii=False, indent=2))
