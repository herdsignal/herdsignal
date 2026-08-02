"""Collect and materialize SEC earnings events for the disjoint history lane."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from herd.append_only_ledger import read_ledger
from herd.sec_earnings_event_ledger_v1 import collect_events
from herd.sec_master_index import resolve_user_agent


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
DEFAULT_LEDGER = ROOT / "data/runtime/action-research/ticker-disjoint-sec-earnings-v1.jsonl"
DEFAULT_CATALOG = ROOT / "data/reports/ticker_disjoint_sec_earnings_census_v1.csv"
DEFAULT_REPORT = ROOT / "data/reports/ticker_disjoint_sec_earnings_census_v1.json"


class TickerDisjointSecCensusError(RuntimeError):
    """Raised when the locked universe or immutable SEC corpus is invalid."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if (
        contract.get("contract_version") != "TICKER_DISJOINT_SEC_EARNINGS_CENSUS_V1"
        or contract.get("status") != "LOCKED_BEFORE_REACTION_OUTCOMES"
        or contract.get("operational_action_ratio") != 0.0
    ):
        raise TickerDisjointSecCensusError("SEC census contract is not locked")
    universe = (ROOT / contract["universe"]["path"]).resolve()
    if not universe.is_relative_to(ROOT) or _sha256(universe) != contract["universe"]["sha256"]:
        raise TickerDisjointSecCensusError("locked disjoint universe changed")
    return contract


def load_cik_universe(contract: dict[str, Any]) -> dict[str, str]:
    frame = pd.read_csv(ROOT / contract["universe"]["path"], dtype={"cik": str})
    if frame["ticker"].duplicated().any() or frame["cik"].isna().any():
        raise TickerDisjointSecCensusError("invalid ticker-CIK universe")
    return {
        str(row.ticker).upper(): str(row.cik).split(".")[0].zfill(10)
        for row in frame.itertuples(index=False)
    }


def materialize_catalog(
    ledger_path: Path,
    universe: dict[str, str],
    catalog_path: Path = DEFAULT_CATALOG,
) -> pd.DataFrame:
    payloads = [row["payload"] for row in read_ledger(ledger_path)]
    frame = pd.DataFrame(payloads)
    expected_columns = [
        "event_id", "ticker", "cik", "accession_number", "accepted_at",
        "filing_date", "report_date", "form", "items", "event_kind",
        "primary_document", "source_url", "source_authority", "information_time",
    ]
    if frame.empty:
        frame = pd.DataFrame(columns=expected_columns)
    else:
        frame = frame[frame["ticker"].isin(universe)].copy()
        if frame["event_id"].duplicated().any():
            raise TickerDisjointSecCensusError("duplicate SEC event identity")
        frame = frame.sort_values(["accepted_at", "event_id"])[expected_columns]
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(catalog_path, index=False)
    return frame


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
    coverage = int(catalog["ticker"].nunique()) if len(catalog) else 0
    report = {
        "report_version": "TICKER_DISJOINT_SEC_EARNINGS_CENSUS_V1",
        "status": (
            "SEC_HISTORY_READY" if coverage == len(universe) else "SEC_HISTORY_PARTIAL"
        ),
        "universe_tickers": len(universe),
        "covered_tickers": coverage,
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
