import json
from pathlib import Path

import pandas as pd
import pytest

from herd.profit_giveback_cycle_execution import (
    adjusted_execution_prices,
    build_action_schedule,
    latest_business_gate,
)
from herd.profit_giveback_economic_v1 import (
    ProfitGivebackEconomicV1Error,
    load_contract,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "data/herd/profit_giveback_economic_v1.json"


def test_contract_locks_zero_authority_and_completed_cycle() -> None:
    contract = load_contract(CONTRACT)
    assert contract["execution_contract"]["trim_fraction_of_current_shares"] == 0.05
    assert contract["execution_contract"]["minimum_reentry_delay_calendar_days"] == 56
    assert (
        contract["decision_policy"]["operational_action_ratio_before_promotion"]
        == 0.0
    )


def test_adjusted_execution_prices_preserve_split_consistency() -> None:
    raw = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2020-01-02", "2020-01-03"]),
            "Open": [100.0, 50.0],
            "Close": [100.0, 50.0],
            "Adj Close": [50.0, 50.0],
        }
    )
    result = adjusted_execution_prices(raw)
    assert result["Open"].tolist() == pytest.approx([50.0, 50.0])
    assert result["Close"].tolist() == pytest.approx([50.0, 50.0])


def test_business_gate_excludes_same_day_acceptance() -> None:
    business = pd.DataFrame(
        {
            "ticker": ["ABC", "ABC"],
            "month_end": pd.to_datetime(["2020-01-31", "2020-02-29"]),
            "business_available_date": pd.to_datetime(
                ["2020-02-01", "2020-03-01"]
            ),
            "latest_fact_accepted_at": pd.to_datetime(
                ["2020-01-30 12:00", "2020-03-06 09:00"]
            ),
            "guard_state": ["PASS", "VETO"],
        }
    )
    state, month_end = latest_business_gate(
        business, "ABC", pd.Timestamp("2020-03-06")
    )
    assert state == "PASS"
    assert month_end == pd.Timestamp("2020-01-31")


def test_schedule_waits_eight_weeks_and_requires_pass() -> None:
    dates = pd.bdate_range("2020-01-02", "2020-05-29")
    prices = pd.DataFrame({"Open": 100.0, "Close": 100.0}, index=dates)
    events = pd.DataFrame(
        {
            "policy_id": ["HERD_GIVEBACK_S1"],
            "ticker": ["ABC"],
            "fold_id": ["F01"],
            "signal_date": pd.to_datetime(["2020-01-03"]),
            "last_observed_session": pd.to_datetime(["2020-01-03"]),
            "trim_fraction": [0.05],
        }
    )
    transitions = pd.DataFrame(
        {
            "ticker": ["ABC", "ABC", "ABC"],
            "HERD_TRANSITION": ["RECOVERING", "RECOVERING", "RECOVERING"],
            "last_observed_session": pd.to_datetime(
                ["2020-02-14", "2020-03-06", "2020-04-03"]
            ),
        }
    )
    business = pd.DataFrame(
        {
            "ticker": ["ABC", "ABC"],
            "month_end": pd.to_datetime(["2020-01-31", "2020-02-29"]),
            "business_available_date": pd.to_datetime(
                ["2020-02-01", "2020-03-01"]
            ),
            "latest_fact_accepted_at": pd.to_datetime(
                ["2020-01-30", "2020-02-28"]
            ),
            "guard_state": ["VETO", "PASS"],
        }
    )
    actions, audit = build_action_schedule(
        policy_id="HERD_GIVEBACK_S1",
        ticker="ABC",
        fold_id="F01",
        prices=prices,
        events=events,
        transitions=transitions,
        business=business,
        minimum_reentry_days=56,
    )
    assert actions.at[pd.Timestamp("2020-01-03"), "action"] == "SELL"
    assert actions.at[pd.Timestamp("2020-02-14"), "action"] == "HOLD"
    assert actions.at[pd.Timestamp("2020-03-06"), "action"] == "BUY"
    assert [row["action"] for row in audit] == ["SELL", "BUY"]


def test_contract_rejects_enabling_actions(tmp_path: Path) -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    payload["decision_policy"]["operational_action_ratio_before_promotion"] = 0.05
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ProfitGivebackEconomicV1Error, match="weakened"):
        load_contract(path)
