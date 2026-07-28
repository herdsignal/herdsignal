from pathlib import Path

import pandas as pd
import pytest

from herd.historical_s1_replay_v1 import (
    HistoricalS1ReplayError,
    attach_outcomes,
    extract_events,
    load_contract,
)


def _panel() -> pd.DataFrame:
    dates = pd.to_datetime([
        "2025-01-03", "2025-01-10", "2025-01-17",
        "2025-02-14", "2025-03-07", "2025-03-14",
    ])
    return pd.DataFrame({
        "ticker": "AAPL",
        "signal_date": dates,
        "last_observed_session": dates,
        "HERD_STATE": [70, 76, 78, 80, 74, 72],
        "HERD_STAGE": ["DRIFT", "RUSH", "RUSH", "RUSH", "DRIFT", "DRIFT"],
        "HERD_TRANSITION": [
            "NEUTRAL", "EXTENDING", "EXTENDING", "EXTENDING",
            "COOLING", "COOLING",
        ],
        "TRANSITION_EVENT": [False, False, False, False, True, True],
        "sector_etf": "XLK",
        "universe_role": "PRIMARY",
    })


def test_extracts_stage_and_transition_events_with_cooldown() -> None:
    contract = load_contract()
    events = extract_events(_panel(), contract)

    assert events["event_kind"].tolist() == [
        "STAGE_ENTRY_RUSH",
        "TRANSITION_COOLING",
    ]
    assert events["episode_id"].is_unique
    assert set(events["era_id"]) == {"ERA_2025_2026"}


def test_outcomes_use_next_session_and_keep_actions_locked() -> None:
    contract = load_contract()
    events = extract_events(_panel(), contract).iloc[[0]]
    dates = pd.bdate_range("2025-01-20", periods=130)
    prices = pd.DataFrame({
        "Date": dates,
        "Open": 100.0,
        "High": 105.0,
        "Low": 95.0,
        "Close": 102.0,
    })

    outcomes = attach_outcomes(events, {"AAPL": prices}, contract)

    assert outcomes["horizon_sessions"].tolist() == [
        5, 10, 20, 21, 40, 60, 63, 126, 130
    ]
    assert {21, 63, 126}.issubset(outcomes["horizon_sessions"])
    assert outcomes["entry_date"].iloc[0] == pd.Timestamp("2025-01-20")
    assert outcomes["total_return"].iloc[0] == pytest.approx(0.02)
    assert outcomes["maximum_adverse_excursion"].iloc[0] == pytest.approx(-0.05)
    assert set(outcomes["operational_action"]) == {"HOLD"}
    assert set(outcomes["operational_action_ratio"]) == {0.0}
    assert not outcomes["direction_prediction"].any()


def test_contract_rejects_action_authority(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[1] / "herd/historical_s1_replay_v1.json"
    contract = source.read_text(encoding="utf-8").replace(
        '"operational_action_ratio": 0.0',
        '"operational_action_ratio": 0.05',
    )
    path = tmp_path / "unsafe.json"
    path.write_text(contract, encoding="utf-8")

    with pytest.raises(HistoricalS1ReplayError):
        load_contract(path)


def test_string_false_does_not_create_transition_event() -> None:
    contract = load_contract()
    panel = _panel()
    panel.loc[2, "HERD_TRANSITION"] = "COOLING"
    panel["TRANSITION_EVENT"] = panel["TRANSITION_EVENT"].map(str)

    events = extract_events(panel, contract)

    assert events["event_kind"].tolist() == [
        "STAGE_ENTRY_RUSH",
        "TRANSITION_COOLING",
    ]
