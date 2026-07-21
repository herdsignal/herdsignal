import numpy as np
import pandas as pd

from herd.weekly_rsi_path_diagnostic import load_measurement, measure_event_path


def test_path_measurement_keeps_future_as_outcome_only():
    measurement, audit = load_measurement()
    assert audit["locked"] is True
    assert measurement["availability"] == "FUTURE_PATH_IS_OUTCOME_ONLY"
    assert measurement["execution_limitations"]["lower_future_close_is_not_proof_of_reentry"] is True


def test_path_metrics_use_all_preregistered_horizons():
    dates = pd.date_range("2020-01-03", periods=40, freq="W-FRI")
    close = np.r_[np.full(10, 100.0), np.linspace(99, 80, 30)]
    weekly = pd.DataFrame({"Adj Close": close}, index=dates)
    result = measure_event_path(weekly, dates[9], [4, 8, 13, 26])
    assert result["h4w_forward_return"] < 0
    assert result["h26w_decline_at_least_10pct"] is True


def test_incomplete_26_week_path_is_excluded():
    dates = pd.date_range("2020-01-03", periods=30, freq="W-FRI")
    weekly = pd.DataFrame({"Adj Close": np.arange(30) + 100}, index=dates)
    assert measure_event_path(weekly, dates[10], [4, 8, 13, 26]) is None
