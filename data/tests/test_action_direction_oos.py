import numpy as np
import pandas as pd

from herd.action_direction_hypotheses import load_registry
from herd.action_direction_oos import _holm, build_event_flags, evaluate_oos


def _frames(days=900, stocks=24):
    dates = pd.bdate_range("2018-01-01", periods=days)
    result = {}
    for index, ticker in enumerate([f"S{i:02d}" for i in range(stocks)] + ["SPY"]):
        base = 100 + np.arange(days) * (0.02 + index / 10000)
        close = base + np.sin(np.arange(days) / (8 + index % 5)) * (2 + index / 20)
        result[ticker] = pd.DataFrame({
            "Date": dates,
            "Open": close * 0.999,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": 1_000_000 + index,
        })
    return result


def test_event_features_do_not_change_when_future_prices_change():
    frames = _frames()
    original, availability = build_event_flags(frames)
    changed = {ticker: frame.copy() for ticker, frame in frames.items()}
    boundary = changed["S00"]["Date"].iloc[-60]
    changed["S00"].loc[changed["S00"]["Date"] >= boundary, ["High", "Low", "Close"]] *= 3
    recalculated, _ = build_event_flags(changed)
    for key in original:
        pd.testing.assert_frame_equal(original[key].loc[:boundary].iloc[:-1], recalculated[key].loc[:boundary].iloc[:-1])
    assert availability["PROFIT_TAKE_RELATIVE_STRENGTH_BREAK"].startswith("DATA_BLOCKED")


def test_holm_is_monotonic():
    rows = [{"raw_p_value": 0.04}, {"raw_p_value": 0.01}, {"raw_p_value": 0.03}]
    _holm(rows)
    ordered = sorted(rows, key=lambda row: row["raw_p_value"])
    assert [row["holm_p_value"] for row in ordered] == sorted(row["holm_p_value"] for row in ordered)


def test_reentry_and_sector_relative_hypotheses_fail_closed():
    frames = _frames(days=1100)
    registry, _ = load_registry()
    folds = [{
        "fold_id": "F1",
        "test_start": "2019-01-01",
        "test_end": "2022-03-31",
    }]
    _, report = evaluate_oos(frames, folds, registry)
    assert report["operational_authorization"] is False
    assert report["blind_holdout_access"] is False
    assert report["decisions"]["PROFIT_TAKE_RELATIVE_STRENGTH_BREAK"].startswith("DATA_BLOCKED")
    assert report["decisions"]["REENTRY_POST_PROFIT_STABILIZATION"].startswith("DEPENDENCY_BLOCKED")
