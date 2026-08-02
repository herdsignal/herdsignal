"""Build an outcome-blind ticker-disjoint universe and its locked S1 history."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from herd.herd_state_s1 import _load_snapshot, build_state_panel, load_contract
from herd.validation_universe import SECTOR_UNIVERSE


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
UNIVERSE_OUTPUT = ROOT / "data/reports/ticker_disjoint_earnings_oos_universe_v1.csv"
STATE_OUTPUT = ROOT / "data/reports/ticker_disjoint_earnings_oos_state_s1.csv.gz"
REPORT_OUTPUT = ROOT / "data/reports/ticker_disjoint_earnings_oos_universe_v1.json"


class TickerDisjointUniverseError(RuntimeError):
    """Raised when the locked selection boundary is changed or unavailable."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_universe_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if (
        contract.get("contract_version")
        != "TICKER_DISJOINT_EARNINGS_OOS_UNIVERSE_V1"
        or contract.get("status") != "LOCKED_BEFORE_EARNINGS_OUTCOMES"
        or contract["limitations"]["operational_action_ratio"] != 0.0
    ):
        raise TickerDisjointUniverseError("ticker-disjoint contract is not locked")
    for item in contract["inputs"]:
        source = (ROOT / item["path"]).resolve()
        if not source.is_relative_to(ROOT) or not source.is_file():
            raise TickerDisjointUniverseError(f"missing locked input: {item['path']}")
        if _sha256(source) != item["sha256"]:
            raise TickerDisjointUniverseError(f"locked input changed: {item['path']}")
    return contract


def select_candidates(
    locked_state: pd.DataFrame,
    inventory: pd.DataFrame,
    manifest: dict[str, Any],
    *,
    minimum_sessions: int,
) -> pd.DataFrame:
    excluded = set(locked_state["ticker"].astype(str).str.upper())
    benchmarks = set(SECTOR_UNIVERSE["benchmark"]) | {"SPY"}
    files = manifest.get("files", {})
    selected = inventory.copy()
    selected["ticker"] = selected["ticker"].astype(str).str.upper()
    selected = selected[
        ~selected["ticker"].isin(excluded | benchmarks)
        & selected["ticker"].map(
            lambda ticker: files.get(ticker, {}).get("role") == "EQUITY"
        )
        & selected["price_rows"].fillna(0).astype(int).ge(minimum_sessions)
        & selected["sector_etf"].notna()
        & selected["cik"].notna()
    ].copy()
    selected = selected.sort_values("ticker").drop_duplicates("ticker")
    if set(selected["ticker"]) & excluded:
        raise TickerDisjointUniverseError("locked 439 leaked into disjoint universe")
    if selected.empty:
        raise TickerDisjointUniverseError("ticker-disjoint universe is empty")
    selected["selection_role"] = "FAST_TICKER_DISJOINT_HISTORICAL_FALSIFICATION"
    selected["selected_without_future_returns"] = True
    return selected[
        [
            "ticker", "company", "cik", "gics_sector", "sector_etf",
            "price_rows", "price_start", "price_end", "selection_role",
            "selected_without_future_returns",
        ]
    ]


def build_outputs(
    universe_output: Path = UNIVERSE_OUTPUT,
    state_output: Path = STATE_OUTPUT,
    report_output: Path = REPORT_OUTPUT,
) -> dict[str, Any]:
    contract = load_universe_contract()
    input_paths = {Path(item["path"]).name: ROOT / item["path"] for item in contract["inputs"]}
    locked_path = input_paths["herd_transition_s1_latest.csv"]
    inventory_path = input_paths["independent_universe_v1.csv"]
    manifest_path = input_paths["manifest.json"]
    locked = pd.read_csv(locked_path)
    inventory = pd.read_csv(inventory_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    selected = select_candidates(
        locked,
        inventory,
        manifest,
        minimum_sessions=int(contract["selection"]["minimum_price_sessions"]),
    )

    output_mapping = selected.set_index("ticker")["sector_etf"].to_dict()
    peer_rows = locked[
        locked["universe_role"].eq("INDEPENDENT_CURRENT_CONSTITUENTS")
    ]
    peer_mapping = peer_rows.drop_duplicates("ticker").set_index("ticker")[
        "sector_etf"
    ].dropna().to_dict()
    required = (
        set(output_mapping)
        | set(output_mapping.values())
        | set(peer_mapping)
        | set(peer_mapping.values())
        | {"SPY"}
    )
    frames = _load_snapshot(manifest_path, required)
    state = build_state_panel(
        frames,
        output_mapping,
        load_contract(),
        "FAST_TICKER_DISJOINT_HISTORICAL_FALSIFICATION",
        peer_mapping=peer_mapping,
        observation_frequency="WEEKLY",
    )
    if set(state["ticker"]) != set(selected["ticker"]):
        raise TickerDisjointUniverseError("S1 state coverage is incomplete")

    universe_output.parent.mkdir(parents=True, exist_ok=True)
    selected.to_csv(universe_output, index=False)
    state.to_csv(state_output, index=False, compression="gzip")
    report = {
        "report_version": "TICKER_DISJOINT_EARNINGS_OOS_UNIVERSE_V1",
        "status": "HISTORICAL_FALSIFICATION_INPUT_READY",
        "ticker_count": int(selected["ticker"].nunique()),
        "state_rows": len(state),
        "first_state_date": str(pd.to_datetime(state["signal_date"]).min().date()),
        "last_state_date": str(pd.to_datetime(state["signal_date"]).max().date()),
        "locked_439_overlap": int(
            len(set(selected["ticker"]) & set(locked["ticker"]))
        ),
        "universe_path": str(universe_output.relative_to(ROOT)),
        "universe_sha256": _sha256(universe_output),
        "state_path": str(state_output.relative_to(ROOT)),
        "state_sha256": _sha256(state_output),
        "survivorship_safe": False,
        "blind_holdout": False,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
    }
    report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(build_outputs(), ensure_ascii=False, indent=2))
