import pandas as pd

from herd.rush_episode_study_v2 import classify_path, extract_episodes, load_protocol


def test_episode_counts_once_until_four_week_reset():
    protocol = load_protocol()
    dates = pd.date_range("2020-01-03", periods=12, freq="W-FRI")
    weekly = pd.DataFrame({
        "extension_votes": [0, 2, 3, 2, 1, 1, 1, 1, 2, 3, 1, 1],
        "last_session": dates,
        "Adj Close": range(100, 112),
        "weekly_rsi_14": 75.0,
        "high_52w_proximity": .98,
        "return_26w": .30,
        "close_to_sma200": 1.2,
    }, index=dates)

    episodes = extract_episodes("TEST", weekly, protocol)

    assert episodes["episode_id"].tolist() == ["TEST-R001", "TEST-R002"]


def test_unresolved_path_is_not_labeled_continuation():
    protocol = load_protocol()
    dates = pd.bdate_range("2020-01-01", periods=140)
    close = pd.Series(100.0, index=dates)
    event = pd.Series({"last_observed_session": dates[0]})

    result = classify_path(close, event, protocol)

    assert result["path_label"] == "UNRESOLVED"


def test_large_unrecovered_decline_is_structural_break():
    protocol = load_protocol()
    dates = pd.bdate_range("2020-01-01", periods=140)
    values = [100.0] + list(pd.Series(range(1, 140)).map(lambda value: 100 - min(value, 30) * .7))
    close = pd.Series(values, index=dates)
    event = pd.Series({"last_observed_session": dates[0]})

    result = classify_path(close, event, protocol)

    assert result["path_label"] == "STRUCTURAL_BREAK"
