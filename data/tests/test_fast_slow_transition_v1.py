import pandas as pd

from herd.fast_slow_transition_v1 import FEATURES, load_protocol, weekly_features


def _prices(end="2022-12-30"):
    dates = pd.bdate_range("2021-01-01", end)
    close = pd.Series(range(100, 100 + len(dates)), dtype=float)
    return pd.DataFrame({
        "Date": dates, "Open": close, "High": close, "Low": close,
        "Close": close, "Adj Close": close, "Volume": 1000,
    })


def test_protocol_keeps_two_prelocked_transition_features():
    protocol = load_protocol()
    assert [row["id"] for row in protocol["candidate_features"]] == FEATURES
    assert protocol["research_boundary"]["operational_action_ratio"] == 0.0


def test_future_prices_do_not_change_prior_weekly_feature():
    protocol = load_protocol()
    base = _prices()
    changed = base.copy()
    cutoff = pd.Timestamp("2022-06-30")
    changed.loc[changed["Date"] > cutoff, "Adj Close"] *= 4
    left = weekly_features(base, protocol)
    right = weekly_features(changed, protocol)
    left = left[left["last_observed_session"] <= cutoff].reset_index(drop=True)
    right = right[right["last_observed_session"] <= cutoff].reset_index(drop=True)
    pd.testing.assert_frame_equal(left, right)
