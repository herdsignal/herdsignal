"""Collect SEC quarterly earnings disclosures into an immutable event ledger."""

from __future__ import annotations

import argparse
import json
import time
from datetime import date
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import requests

from herd.append_only_ledger import append_unique
from herd.sec_master_index import resolve_user_agent


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_UNIVERSE = ROOT / "data/reports/herd_transition_s1_latest.csv"
DEFAULT_IDENTITIES = ROOT / "data/reports/sec_time_valid_ticker_cik_intervals_v5.csv"
DEFAULT_LEDGER = ROOT / "data/runtime/action-research/sec-earnings-events-v1.jsonl"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ELIGIBLE_FORMS = {"8-K", "8-K/A", "10-Q", "10-Q/A"}


class SecEarningsEventError(RuntimeError):
    """Raised when SEC source timing or issuer identity is ambiguous."""


def load_universe(
    universe_path: Path = DEFAULT_UNIVERSE,
    identity_path: Path = DEFAULT_IDENTITIES,
) -> dict[str, str]:
    universe = pd.read_csv(universe_path, dtype={"ticker": str})
    identities = pd.read_csv(identity_path, dtype={"cik": str})
    tickers = set(universe["ticker"].str.upper())
    ticker_keys = {ticker: ticker.replace("-", "").replace(".", "") for ticker in tickers}
    identities["canonical_symbol"] = identities["canonical_symbol"].str.upper()
    identities["symbol_key"] = identities["canonical_symbol"].str.replace(
        r"[-.]", "", regex=True
    )
    identities = identities[
        identities["symbol_key"].isin(set(ticker_keys.values()))
        & identities["status"].eq("TIME_VALID_CIK_VERIFIED")
    ].copy()
    identities["cik"] = identities["cik"].str.zfill(10)
    # A ticker can legitimately have more than one historical CIK after a merger or
    # legal-entity succession (for example BG and BLK).  Prospective collection must
    # use the latest evidenced interval, not reject the whole universe or silently
    # pick the first row in file order.
    identities["valid_to_sort"] = pd.to_datetime(
        identities["valid_to"], errors="coerce"
    )
    if identities["valid_to_sort"].isna().any():
        invalid = sorted(
            identities.loc[identities["valid_to_sort"].isna(), "canonical_symbol"]
            .unique()
        )
        raise SecEarningsEventError(f"invalid CIK interval dates: {invalid[:10]}")
    latest_dates = identities.groupby("symbol_key")["valid_to_sort"].transform(
        "max"
    )
    latest = identities[identities["valid_to_sort"].eq(latest_dates)].copy()
    ambiguous = sorted(
        latest.groupby("symbol_key")["cik"].nunique().loc[lambda row: row.ne(1)].index
    )
    if ambiguous:
        raise SecEarningsEventError(f"ambiguous latest CIKs: {ambiguous[:10]}")
    by_key = latest.drop_duplicates("symbol_key").set_index("symbol_key")["cik"].to_dict()
    mapping = {
        ticker: by_key[key] for ticker, key in ticker_keys.items() if key in by_key
    }
    missing = sorted(tickers - set(mapping))
    if missing:
        raise SecEarningsEventError(f"unmapped current tickers: {missing[:10]}")
    return dict(sorted(mapping.items()))


def _columnar_rows(filings: dict[str, Any]) -> list[dict[str, Any]]:
    if not filings:
        return []
    lengths = {len(value) for value in filings.values() if isinstance(value, list)}
    if len(lengths) != 1:
        raise SecEarningsEventError("SEC submissions columns have unequal lengths")
    count = lengths.pop() if lengths else 0
    return [
        {key: value[index] for key, value in filings.items() if isinstance(value, list)}
        for index in range(count)
    ]


def extract_events(
    ticker: str,
    cik: str,
    payloads: list[tuple[str, dict[str, Any]]],
    *,
    accepted_on_or_after: date | None = None,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for source_url, payload in payloads:
        recent = payload.get("filings", {}).get("recent") if "filings" in payload else payload
        for row in _columnar_rows(recent or {}):
            form = str(row.get("form", "")).upper()
            items = str(row.get("items", ""))
            item_tokens = {item.strip() for item in items.split(",") if item.strip()}
            event_kind = None
            if form in {"8-K", "8-K/A"} and "2.02" in item_tokens:
                event_kind = "EARNINGS_RESULT_8K_ITEM_2_02"
            elif form in {"10-Q", "10-Q/A"}:
                event_kind = "QUARTERLY_REPORT_10Q"
            if form not in ELIGIBLE_FORMS or event_kind is None:
                continue
            accepted_at = str(row.get("acceptanceDateTime", ""))
            if not accepted_at:
                raise SecEarningsEventError(
                    f"missing SEC acceptance time: {ticker} {row.get('accessionNumber')}"
                )
            accepted = pd.Timestamp(accepted_at)
            if accepted.tzinfo is None:
                accepted = accepted.tz_localize("UTC")
            else:
                accepted = accepted.tz_convert("UTC")
            if accepted_on_or_after and accepted.date() < accepted_on_or_after:
                continue
            accession = str(row.get("accessionNumber", ""))
            if not accession:
                raise SecEarningsEventError("SEC event is missing accession number")
            events.append({
                "event_id": f"SEC-EARNINGS-{cik}-{accession}",
                "ticker": ticker,
                "cik": cik,
                "accession_number": accession,
                "accepted_at": accepted.isoformat().replace("+00:00", "Z"),
                "filing_date": str(row.get("filingDate", "")),
                "report_date": str(row.get("reportDate", "")),
                "form": form,
                "items": items,
                "event_kind": event_kind,
                "primary_document": str(row.get("primaryDocument", "")),
                "source_url": source_url,
                "source_authority": "SEC_EDGAR_SUBMISSIONS_API",
                "information_time": "EDGAR_ACCEPTANCE_DATETIME",
            })
    unique: dict[str, dict[str, Any]] = {}
    for event in events:
        existing = unique.get(event["event_id"])
        if existing is not None and existing != event:
            raise SecEarningsEventError(f"conflicting SEC event: {event['event_id']}")
        unique[event["event_id"]] = event
    return sorted(unique.values(), key=lambda row: (row["accepted_at"], row["event_id"]))


def _get_json(session: requests.Session, url: str) -> dict[str, Any]:
    response = session.get(url, timeout=60)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise SecEarningsEventError(f"SEC response is not an object: {url}")
    return payload


def fetch_submission_payloads(
    cik: str,
    session: requests.Session,
    *,
    include_historical_files: bool,
    delay_seconds: float,
) -> list[tuple[str, dict[str, Any]]]:
    url = SUBMISSIONS_URL.format(cik=cik)
    root = _get_json(session, url)
    payloads = [(url, root)]
    if include_historical_files:
        for item in root.get("filings", {}).get("files", []):
            name = str(item.get("name", ""))
            if not name:
                continue
            historical_url = f"https://data.sec.gov/submissions/{name}"
            time.sleep(delay_seconds)
            payloads.append((historical_url, _get_json(session, historical_url)))
    return payloads


def collect_events(
    universe: dict[str, str],
    ledger_path: Path,
    *,
    user_agent: str,
    accepted_on_or_after: date | None,
    include_historical_files: bool = False,
    delay_seconds: float = 0.12,
    payload_loader: Callable[[str], list[tuple[str, dict[str, Any]]]] | None = None,
) -> dict[str, Any]:
    if delay_seconds < 0.11:
        raise SecEarningsEventError("SEC request delay must remain at least 0.11 seconds")
    session = requests.Session()
    session.headers.update({
        "User-Agent": user_agent,
        "Accept-Encoding": "gzip, deflate",
    })
    events: list[dict[str, Any]] = []
    for index, (ticker, cik) in enumerate(sorted(universe.items())):
        if index:
            time.sleep(delay_seconds)
        payloads = (
            payload_loader(cik)
            if payload_loader is not None
            else fetch_submission_payloads(
                cik,
                session,
                include_historical_files=include_historical_files,
                delay_seconds=delay_seconds,
            )
        )
        events.extend(
            extract_events(
                ticker, cik, payloads, accepted_on_or_after=accepted_on_or_after
            )
        )
    result = append_unique(ledger_path, events, identity_field="event_id")
    return {
        "status": "SEC_EARNINGS_LEDGER_UPDATED",
        "issuers_scanned": len(universe),
        "events_discovered": len(events),
        **result,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--identities", type=Path, default=DEFAULT_IDENTITIES)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--accepted-on-or-after", type=date.fromisoformat)
    parser.add_argument("--include-historical-files", action="store_true")
    args = parser.parse_args()
    print(json.dumps(collect_events(
        load_universe(args.universe, args.identities),
        args.ledger,
        user_agent=resolve_user_agent(args.env_file),
        accepted_on_or_after=args.accepted_on_or_after,
        include_historical_files=args.include_historical_files,
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
