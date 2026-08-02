"""Best-effort SEC earnings-event intake for the locked Rush hypothesis."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable

import pandas as pd

from herd.sec_earnings_event_ledger_v1 import (
    DEFAULT_IDENTITIES,
    DEFAULT_LEDGER,
    DEFAULT_UNIVERSE,
    collect_events,
    load_universe,
)
from herd.sec_master_index import SecMasterIndexError, resolve_user_agent


ROOT = Path(__file__).resolve().parents[2]
FIRST_ELIGIBLE_ACCEPTANCE_DATE = date(2026, 8, 3)


def load_current_rush_universe(
    state_path: Path = DEFAULT_UNIVERSE,
    identity_path: Path = DEFAULT_IDENTITIES,
) -> dict[str, str]:
    state = pd.read_csv(state_path, dtype={"ticker": str, "HERD_STAGE": str})
    required = {"ticker", "HERD_STAGE"}
    if not required.issubset(state.columns):
        raise ValueError(f"weekly S1 is missing columns: {sorted(required - set(state.columns))}")
    rush = set(
        state.loc[state["HERD_STAGE"].str.upper().eq("RUSH"), "ticker"]
        .str.upper()
        .dropna()
    )
    identities = load_universe(state_path, identity_path)
    return {ticker: identities[ticker] for ticker in sorted(rush)}


def collect_current_rush_earnings_events(
    *,
    state_path: Path = DEFAULT_UNIVERSE,
    identity_path: Path = DEFAULT_IDENTITIES,
    ledger_path: Path = DEFAULT_LEDGER,
    env_file: Path = ROOT / ".env",
    collector: Callable[..., dict] = collect_events,
) -> dict:
    """Collect data without allowing research failure to mutate operation policy."""
    universe = load_current_rush_universe(state_path, identity_path)
    if not universe:
        return {
            "status": "NO_CURRENT_RUSH_ISSUERS",
            "issuers_scanned": 0,
            "appended": 0,
            "operational_action": "HOLD",
            "operational_action_ratio": 0.0,
        }
    try:
        user_agent = resolve_user_agent(env_file)
    except SecMasterIndexError as exc:
        return {
            "status": "SKIPPED_SEC_USER_AGENT_NOT_CONFIGURED",
            "issuers_scanned": 0,
            "appended": 0,
            "detail": str(exc),
            "operational_action": "HOLD",
            "operational_action_ratio": 0.0,
        }
    return collector(
        universe,
        ledger_path,
        user_agent=user_agent,
        accepted_on_or_after=FIRST_ELIGIBLE_ACCEPTANCE_DATE,
        include_historical_files=False,
    )
