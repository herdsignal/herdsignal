"""Build an outcome-blind second earnings OOS cohort from verified S&P removals."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from herd.herd_state_s1 import _load_snapshot, build_state_panel, load_contract as load_state_contract
from herd.long_price_snapshot import create_snapshot, verify_snapshot


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
CANDIDATE_OUTPUT = ROOT / "data/reports/ticker_disjoint_earnings_oos_expansion_v2_candidates.csv"
UNIVERSE_OUTPUT = ROOT / "data/reports/ticker_disjoint_earnings_oos_expansion_v2.csv"
STATE_OUTPUT = ROOT / "data/reports/ticker_disjoint_earnings_oos_expansion_v2_state_s1.csv.gz"
REPORT_OUTPUT = ROOT / "data/reports/ticker_disjoint_earnings_oos_expansion_v2.json"
LOCK_OUTPUT = ROOT / "data/reports/ticker_disjoint_earnings_oos_expansion_v2_lock.json"
EVIDENCE_ROOT = ROOT / "data/reference/point_in_time/spglobal-releases-merged-v4-20160718-20260717/evidence"

SECTOR_ETF = {
    "Communication Services": "XLC",
    "Telecommunication Services": "XLC",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Financials": "XLF",
    "Health Care": "XLV",
    "Industrials": "XLI",
    "Information Technology": "XLK",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
}


class ExpansionUniverseError(RuntimeError):
    """Raised when the former-constituent selection or immutable input drifts."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_expansion_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if (
        contract.get("contract_version") != "TICKER_DISJOINT_EARNINGS_OOS_EXPANSION_V2"
        or contract.get("status") != "LOCKED_BEFORE_PRICE_AND_EARNINGS_OUTCOMES"
        or contract["limitations"]["operational_action_ratio"] != 0.0
    ):
        raise ExpansionUniverseError("expansion contract is not locked")
    for item in contract["inputs"]:
        source = (ROOT / item["path"]).resolve()
        if not source.is_relative_to(ROOT) or not source.is_file():
            raise ExpansionUniverseError(f"missing locked input: {item['path']}")
        if _sha256(source) != item["sha256"]:
            raise ExpansionUniverseError(f"locked input changed: {item['path']}")
    return contract


def extract_official_sector(document: Path, ticker: str) -> str | None:
    """Return the GICS sector only when an official table row names the ticker."""
    if not document.is_file() or _sha256(document) != document.stem:
        return None
    try:
        tables = pd.read_html(document)
    except (ValueError, ImportError):
        return None
    normalized_ticker = ticker.strip().upper()
    matches: set[str] = set()
    for table in tables:
        for _, row in table.iterrows():
            cells = [str(value).replace("\xa0", " ").strip() for value in row.tolist()]
            if normalized_ticker not in {value.upper() for value in cells}:
                continue
            matches.update(value for value in cells if value in SECTOR_ETF)
    if len(matches) > 1:
        raise ExpansionUniverseError(f"conflicting official sectors for {ticker}: {sorted(matches)}")
    return next(iter(matches), None)


def select_former_constituents(
    events: pd.DataFrame,
    locked_tickers: set[str],
    v1_tickers: set[str],
    evidence_root: Path = EVIDENCE_ROOT,
) -> tuple[pd.DataFrame, dict[str, int]]:
    rows = events[
        events["action"].eq("REMOVE")
        & events["event_status"].eq("VERIFIED_OFFICIAL_EVENT")
    ].copy()
    rows["ticker"] = rows["ticker"].astype(str).str.upper()
    rows = rows[~rows["ticker"].isin(locked_tickers | v1_tickers)]
    rows = rows.sort_values(["effective_date", "ticker"]).drop_duplicates("ticker", keep="last")

    records: list[dict[str, Any]] = []
    exclusions = {"MISSING_EVENT_TIME_CIK": 0, "MISSING_OFFICIAL_SECTOR": 0}
    for row in rows.itertuples(index=False):
        cik = "" if pd.isna(row.cik) else str(row.cik).split(".")[0].zfill(10)
        if not cik:
            exclusions["MISSING_EVENT_TIME_CIK"] += 1
            continue
        document = evidence_root / f"{row.sp_source_sha256}.html"
        sector = extract_official_sector(document, row.ticker)
        if sector is None:
            exclusions["MISSING_OFFICIAL_SECTOR"] += 1
            continue
        records.append({
            "ticker": row.ticker,
            "cik": cik,
            "gics_sector": sector,
            "sector_etf": SECTOR_ETF[sector],
            "verified_removal_date": row.effective_date,
            "sp_source_url": row.sp_source_url,
            "sp_source_sha256": row.sp_source_sha256,
            "identity_basis": "VERIFIED_S&P_REMOVAL_EVENT_CIK",
            "sector_basis": "OFFICIAL_S&P_RELEASE_TABLE_ROW",
            "selected_without_price_or_earnings_outcomes": True,
        })
    selected = pd.DataFrame(records).sort_values("ticker").reset_index(drop=True)
    if selected.empty:
        raise ExpansionUniverseError("no former constituent passed source gates")
    if set(selected["ticker"]) & (locked_tickers | v1_tickers):
        raise ExpansionUniverseError("ticker-disjoint boundary was violated")
    if selected["ticker"].duplicated().any() or selected["cik"].duplicated().any():
        raise ExpansionUniverseError("ambiguous ticker or CIK in expansion candidates")
    return selected, exclusions


def build_candidates(output: Path = CANDIDATE_OUTPUT) -> dict[str, Any]:
    contract = load_expansion_contract()
    paths = {Path(item["path"]).name: ROOT / item["path"] for item in contract["inputs"]}
    events = pd.read_csv(paths["integrated_event_ledger.csv"], dtype={"cik": str})
    locked = set(pd.read_csv(paths["herd_transition_s1_latest.csv"])["ticker"].astype(str).str.upper())
    v1 = set(pd.read_csv(paths["ticker_disjoint_earnings_oos_universe_v1.csv"])["ticker"].astype(str).str.upper())
    selected, exclusions = select_former_constituents(events, locked, v1)
    output.parent.mkdir(parents=True, exist_ok=True)
    selected.to_csv(output, index=False)
    return {
        "report_version": "TICKER_DISJOINT_EARNINGS_OOS_EXPANSION_V2_CANDIDATES",
        "status": "OUTCOME_BLIND_PRICE_COLLECTION_QUEUE_READY",
        "candidate_tickers": len(selected),
        "excluded_locked_tickers": len(locked),
        "excluded_v1_tickers": len(v1),
        "source_exclusions": exclusions,
        "candidate_path": str(output.relative_to(ROOT)),
        "candidate_sha256": _sha256(output),
        "future_price_outcomes_read": False,
        "operational_action_ratio": 0.0,
    }


def collect_prices(snapshot_id: str, snapshot_root: Path) -> Path:
    contract = load_expansion_contract()
    candidates = pd.read_csv(CANDIDATE_OUTPUT)
    return create_snapshot(
        snapshot_id,
        start=date.fromisoformat(contract["price_period"]["start_inclusive"]),
        end=date.fromisoformat(contract["price_period"]["end_exclusive"]),
        equities=candidates["ticker"].tolist(),
        sector_etfs=sorted(set(candidates["sector_etf"])),
        root=snapshot_root,
        allow_equity_failures=True,
    )


def finalize_snapshot(snapshot: Path) -> dict[str, Any]:
    contract = load_expansion_contract()
    snapshot = snapshot.resolve()
    if not snapshot.is_relative_to(ROOT):
        raise ExpansionUniverseError("snapshot must be inside the repository")
    manifest = verify_snapshot(snapshot)
    candidates = pd.read_csv(CANDIDATE_OUTPUT, dtype={"cik": str})
    minimum = int(contract["selection"]["minimum_price_sessions"])
    records = []
    price_exclusions: dict[str, str] = {}
    for row in candidates.itertuples(index=False):
        metadata = manifest["files"].get(row.ticker)
        if metadata is None:
            price_exclusions[row.ticker] = "PRICE_COLLECTION_FAILED"
            continue
        if metadata["role"] != "EQUITY":
            price_exclusions[row.ticker] = "NON_EQUITY_PRICE_SERIES"
            continue
        if int(metadata["rows"]) < minimum:
            price_exclusions[row.ticker] = "INSUFFICIENT_PRICE_SESSIONS_OR_REUSED_TICKER"
            continue
        records.append({
            **row._asdict(),
            "price_rows": int(metadata["rows"]),
            "price_start": metadata["start"],
            "price_end": metadata["end"],
            "selection_role": "FORMER_CONSTITUENT_TICKER_DISJOINT_FALSIFICATION",
        })
    selected = pd.DataFrame(records)
    if selected.empty:
        raise ExpansionUniverseError("immutable snapshot has no eligible expansion ticker")

    locked = pd.read_csv(ROOT / "data/reports/herd_transition_s1_latest.csv")
    peer_rows = locked[locked["universe_role"].eq("INDEPENDENT_CURRENT_CONSTITUENTS")]
    peer_mapping = peer_rows.drop_duplicates("ticker").set_index("ticker")["sector_etf"].dropna().to_dict()
    output_mapping = selected.set_index("ticker")["sector_etf"].to_dict()
    required = set(output_mapping) | set(output_mapping.values()) | set(peer_mapping) | set(peer_mapping.values()) | {"SPY"}

    # Peer breadth prices remain in the original immutable current-constituent snapshot.
    peer_snapshot = ROOT / "data/snapshots/yf-independent-current-sp500-20260721/manifest.json"
    peer_frames = _load_snapshot(peer_snapshot, set(peer_mapping) | set(peer_mapping.values()) | {"SPY"})
    expansion_frames = _load_snapshot(snapshot / "manifest.json", set(output_mapping) | set(output_mapping.values()) | {"SPY"})
    frames = {**peer_frames, **expansion_frames}
    if not required.issubset(frames):
        raise ExpansionUniverseError("price frames are incomplete after snapshot merge")
    state = build_state_panel(
        frames,
        output_mapping,
        load_state_contract(),
        "FORMER_CONSTITUENT_TICKER_DISJOINT_FALSIFICATION",
        peer_mapping=peer_mapping,
        observation_frequency="WEEKLY",
    )
    if set(state["ticker"]) != set(selected["ticker"]):
        raise ExpansionUniverseError("S1 state coverage is incomplete")

    UNIVERSE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    selected.to_csv(UNIVERSE_OUTPUT, index=False)
    state.to_csv(
        STATE_OUTPUT,
        index=False,
        compression={"method": "gzip", "compresslevel": 9, "mtime": 0},
    )
    lock = {
        "lock_version": "TICKER_DISJOINT_EARNINGS_OOS_EXPANSION_V2_INPUT_LOCK",
        "status": "LOCKED_BEFORE_EARNINGS_REACTION_OUTCOMES",
        "universe_path": str(UNIVERSE_OUTPUT.relative_to(ROOT)),
        "universe_sha256": _sha256(UNIVERSE_OUTPUT),
        "state_path": str(STATE_OUTPUT.relative_to(ROOT)),
        "state_sha256": _sha256(STATE_OUTPUT),
        "price_manifest_path": str((snapshot / "manifest.json").relative_to(ROOT)),
        "price_manifest_sha256": _sha256(snapshot / "manifest.json"),
        "future_earnings_reaction_outcomes_read": False,
    }
    LOCK_OUTPUT.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n")
    report = {
        "report_version": "TICKER_DISJOINT_EARNINGS_OOS_EXPANSION_V2",
        "status": "EXPANSION_INPUT_READY" if len(selected) >= 20 else "EXPANSION_COVERAGE_BLOCKED",
        "candidate_tickers": len(candidates),
        "eligible_tickers": len(selected),
        "state_rows": len(state),
        "first_state_date": str(pd.to_datetime(state["signal_date"]).min().date()),
        "last_state_date": str(pd.to_datetime(state["signal_date"]).max().date()),
        "minimum_ticker_gate": 20,
        "minimum_ticker_gate_passed": len(selected) >= 20,
        "price_exclusions": dict(sorted(price_exclusions.items())),
        "snapshot_collection_failures": manifest["failures"],
        "survivorship_safe": False,
        "blind_holdout": False,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
        "input_lock_path": str(LOCK_OUTPUT.relative_to(ROOT)),
    }
    REPORT_OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build-candidates")
    collect = sub.add_parser("collect-prices")
    collect.add_argument("--snapshot-id", required=True)
    collect.add_argument("--snapshot-root", type=Path, default=ROOT / "data/snapshots")
    finalize = sub.add_parser("finalize")
    finalize.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build-candidates":
        print(json.dumps(build_candidates(), ensure_ascii=False, indent=2))
    elif args.command == "collect-prices":
        print(collect_prices(args.snapshot_id, args.snapshot_root))
    else:
        print(json.dumps(finalize_snapshot(args.snapshot), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
