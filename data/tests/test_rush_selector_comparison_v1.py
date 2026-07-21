import pandas as pd

from herd.rush_selector_comparison_v1 import (
    choose_selector,
    collapse_v61_rush_events,
    intersect_events,
    load_protocol,
)


def test_protocol_is_locked_and_cannot_authorize_actions():
    protocol = load_protocol()
    assert protocol["status"] == "LOCKED_BEFORE_SELECTOR_COMPARISON"
    assert protocol["policy"]["operational_action_authority"] is False


def test_v61_events_collapse_repeated_rush_actions():
    protocol = load_protocol()
    events = pd.DataFrame({
        "ticker": ["AAA"] * 4,
        "signal_date": ["2020-01-01", "2020-01-29", "2020-03-20", "2020-04-01"],
        "action": ["SELL"] * 4,
        "regime": ["HEALTHY_RUSH"] * 4,
    })
    collapsed = collapse_v61_rush_events(events, protocol)
    assert collapsed["signal_date"].dt.strftime("%Y-%m-%d").tolist() == ["2020-01-01", "2020-03-20"]


def test_intersection_uses_later_observation_and_is_one_to_one():
    protocol = load_protocol()
    v61 = pd.DataFrame({"ticker": ["AAA"], "episode_id": ["V1"], "signal_date": pd.to_datetime(["2020-01-03"]), "last_observed_session": pd.to_datetime(["2020-01-03"]), "source_regime": ["HEALTHY_RUSH"]})
    price = pd.DataFrame({"ticker": ["AAA"], "episode_id": ["P1"], "signal_date": pd.to_datetime(["2020-01-10"]), "last_observed_session": pd.to_datetime(["2020-01-10"])})
    result = intersect_events(v61, price, protocol)
    assert len(result) == 1
    assert result.iloc[0]["last_observed_session"] == pd.Timestamp("2020-01-10")


def test_selector_gate_fails_closed_when_no_candidate_is_eligible():
    decision = choose_selector([
        {"selector": "A", "eligible_for_discovery_selection": False, "selection_utility": 1.0, "median_annual_episodes_per_ticker": 1.0}
    ], load_protocol())
    assert decision == {"status": "NO_SELECTOR_PASSED_GATE", "selected": None}
