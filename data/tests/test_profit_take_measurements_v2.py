import copy

import numpy as np
import pandas as pd
import pytest

from herd.profit_take_measurements_v2 import (
    ProfitTakeMeasurementV2Error,
    calculate_measurements,
    expanding_percentile,
    load_registry,
    validate_registry,
)


def test_registry_locks_four_independent_hypotheses():
    registry, audit = load_registry()
    assert audit["hypothesis_count"] == 4
    changed = copy.deepcopy(registry)
    changed["hypotheses"][0]["event_percentiles"] = [0.75, 0.9]
    with pytest.raises(ProfitTakeMeasurementV2Error, match="percentiles"):
        validate_registry(changed)


def test_expanding_percentile_never_uses_current_or_future_value():
    base = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    changed_future = base.copy()
    changed_future.iloc[-1] = 999.0
    first = expanding_percentile(base, minimum_history=2)
    second = expanding_percentile(changed_future, minimum_history=2)
    pd.testing.assert_series_equal(first.iloc[:-1], second.iloc[:-1])
    assert first.iloc[2] == 1.0


def test_measurements_are_separate_and_positive_trend_gate_is_applied():
    index = pd.bdate_range("2018-01-01", periods=900)
    stock = pd.Series(np.exp(np.linspace(0, 1.2, len(index))), index=index)
    sector = pd.Series(np.exp(np.linspace(0, 0.5, len(index))), index=index)
    spy = pd.Series(np.exp(np.linspace(0, 0.4, len(index))), index=index)
    result = calculate_measurements(stock, sector, spy, minimum_history=100)
    assert {"relative_extension", "trend_deceleration", "relative_break", "downside_expansion"}.issubset(result.columns)
    assert result["relative_extension"].dropna().iloc[-1] > 0
