from __future__ import annotations

import pandas as pd
import pytest

from herd.rush_negative_earnings_reaction_oos_v1 import (
    ProspectiveHypothesisError,
    evaluate,
    load_protocol,
)


def _row(index: int, *, date: str = "2026-08-10") -> dict:
    return {
        "event_id": f"E{index}", "ticker": f"T{index % 20}", "sector_etf": "XLK",
        "sec_accepted_at": f"{date}T20:00:00Z",
        "reaction_confirmation_session": "2026-08-13",
        "state_observation_date": "2026-08-07", "herd_stage": "RUSH",
        "stock_reaction_3s": -0.08, "sector_reaction_3s": -0.01,
        "outcome_maturity_date": "2027-02-12",
        "outcome_label": "ECONOMIC_REBUY_OPPORTUNITY", "completed_cycle": True,
        "hold_terminal_value": 1.0, "candidate_terminal_value_base": 1.01,
        "candidate_terminal_value_stress": 1.005,
        "base_round_trip_cost_bps": 30, "stress_round_trip_cost_bps": 70,
    }


def test_missing_runtime_input_is_a_waiting_state(tmp_path) -> None:
    from herd.rush_negative_earnings_reaction_oos_v1 import run

    result = run(tmp_path / "missing.csv")
    assert result["status"] == "WAITING_FOR_PROSPECTIVE_OOS"
    assert result["operational_action"] == "HOLD"
    assert result["operational_action_ratio"] == 0.0


def test_historical_backfill_is_rejected() -> None:
    row = _row(1, date="2026-08-01")
    with pytest.raises(ProspectiveHypothesisError, match="backfill"):
        evaluate(pd.DataFrame([row]), load_protocol())


def test_non_trigger_row_is_rejected() -> None:
    row = _row(1)
    row["stock_reaction_3s"] = -0.02
    with pytest.raises(ProspectiveHypothesisError, match="negative reaction"):
        evaluate(pd.DataFrame([row]), load_protocol())


def test_missing_mature_terminal_value_is_rejected() -> None:
    row = _row(1)
    row["candidate_terminal_value_stress"] = None
    with pytest.raises(ProspectiveHypothesisError, match="terminal values"):
        evaluate(pd.DataFrame([row]), load_protocol())


def test_gate_can_pass_only_with_mature_costed_multi_year_cycles() -> None:
    rows = []
    counter = 0
    for year in (2026, 2027, 2028):
        for offset in range(14):
            row = _row(counter, date=f"{year}-08-10")
            row["reaction_confirmation_session"] = f"{year}-08-13"
            row["state_observation_date"] = f"{year}-08-07"
            row["outcome_maturity_date"] = f"{year + 1}-02-12"
            rows.append(row)
            counter += 1
    result = evaluate(pd.DataFrame(rows), load_protocol())
    assert result["status"] == "PROSPECTIVE_GATE_PASSED"
    assert result["direction_evidence_admitted"] is True
    assert result["candidate_action_enabled"] is False
    assert result["operational_action_ratio"] == 0.0
