import pandas as pd
import pytest

from herd.historical_s1_dependency_audit_v1 import (
    HistoricalS1DependencyAuditError,
    audit_dependency,
    build_regime_context,
    load_contract,
)


def _context() -> pd.DataFrame:
    return build_regime_context(pd.DataFrame({
        "ticker": ["A", "B", "A", "B"],
        "signal_date": pd.to_datetime([
            "2025-01-03", "2025-01-03", "2025-01-10", "2025-01-10"
        ]),
        "sector_etf": ["XLK", "XLF", "XLK", "XLF"],
        "HERD_STATE": [80, 40, 60, 20],
    }))


def _ledger() -> pd.DataFrame:
    rows = []
    for episode, ticker, sector, date, state in [
        ("e1", "A", "XLK", "2025-01-03", 80),
        ("e2", "B", "XLF", "2025-01-10", 20),
    ]:
        for horizon in [5, 10]:
            rows.append({
                "episode_id": episode,
                "era_id": "ERA_2025_2026",
                "universe_role": "PRIMARY",
                "ticker": ticker,
                "sector_etf": sector,
                "signal_date": date,
                "event_kind": "STAGE_ENTRY_RUSH",
                "horizon_sessions": horizon,
                "total_return": 0.01,
                "maximum_favorable_excursion": 0.02,
                "maximum_adverse_excursion": -0.01,
                "direction_prediction": False,
                "operational_action": "HOLD",
                "operational_action_ratio": 0.0,
                "herd_state": state,
            })
    return pd.DataFrame(rows)


def test_builds_market_and_sector_regimes_without_future_outcomes() -> None:
    context = _context()

    first_week = context[context["signal_date"].eq(pd.Timestamp("2025-01-03"))]
    assert set(first_week["market_herd_stage"]) == {"DRIFT"}
    assert dict(zip(
        first_week["sector_etf"], first_week["sector_herd_stage"]
    )) == {"XLF": "CALM", "XLK": "RUSH"}


def test_dependency_audit_counts_independence_units() -> None:
    contract = load_contract()
    contract["diagnostic_gates"]["minimum_signal_weeks"] = 2
    contract["diagnostic_gates"]["maximum_single_week_episode_fraction"] = 0.5

    report, summary = audit_dependency(_ledger(), _context(), contract)

    assert report["status"] == "DEPENDENCY_DIAGNOSTIC_COMPLETE"
    assert report["independence_units"] == {
        "raw_horizon_rows": 4,
        "episodes": 2,
        "tickers": 2,
        "signal_weeks": 2,
        "sector_signal_weeks": 2,
        "eras": 1,
    }
    assert set(summary["horizon_sessions"]) == {5, 10}
    assert report["operational_action_ratio"] == 0.0


def test_dependency_audit_rejects_action_rows() -> None:
    contract = load_contract()
    ledger = _ledger()
    ledger.loc[0, "operational_action"] = "REDUCE"

    with pytest.raises(HistoricalS1DependencyAuditError):
        audit_dependency(ledger, _context(), contract)
