from pathlib import Path

import pandas as pd

from scheduler.earnings_event_intake import (
    FIRST_ELIGIBLE_ACCEPTANCE_DATE,
    collect_current_rush_earnings_events,
    load_current_rush_universe,
)


def test_load_current_rush_universe_filters_before_collection(tmp_path: Path):
    state = tmp_path / "state.csv"
    identity = tmp_path / "identity.csv"
    pd.DataFrame([
        {"ticker": "AAA", "HERD_STAGE": "RUSH"},
        {"ticker": "BBB", "HERD_STAGE": "CALM"},
    ]).to_csv(state, index=False)
    pd.DataFrame([
        {
            "canonical_symbol": "AAA", "cik": "1", "valid_to": "2026-01-01",
            "status": "TIME_VALID_CIK_VERIFIED",
        },
        {
            "canonical_symbol": "BBB", "cik": "2", "valid_to": "2026-01-01",
            "status": "TIME_VALID_CIK_VERIFIED",
        },
    ]).to_csv(identity, index=False)

    assert load_current_rush_universe(state, identity) == {"AAA": "0000000001"}


def test_collection_keeps_locked_start_and_hold_policy(tmp_path: Path):
    state = tmp_path / "state.csv"
    identity = tmp_path / "identity.csv"
    env = tmp_path / ".env"
    ledger = tmp_path / "events.jsonl"
    pd.DataFrame([{"ticker": "AAA", "HERD_STAGE": "RUSH"}]).to_csv(
        state, index=False
    )
    pd.DataFrame([{
        "canonical_symbol": "AAA", "cik": "1", "valid_to": "2026-01-01",
        "status": "TIME_VALID_CIK_VERIFIED",
    }]).to_csv(identity, index=False)
    env.write_text("SEC_USER_AGENT=HerdSignal test test@example.com\n")
    seen = {}

    def collector(universe, output, **kwargs):
        seen.update({"universe": universe, "output": output, **kwargs})
        return {"status": "SEC_EARNINGS_LEDGER_UPDATED", "appended": 0}

    result = collect_current_rush_earnings_events(
        state_path=state,
        identity_path=identity,
        ledger_path=ledger,
        env_file=env,
        collector=collector,
    )

    assert result["status"] == "SEC_EARNINGS_LEDGER_UPDATED"
    assert seen["universe"] == {"AAA": "0000000001"}
    assert seen["accepted_on_or_after"] == FIRST_ELIGIBLE_ACCEPTANCE_DATE
    assert seen["include_historical_files"] is False
