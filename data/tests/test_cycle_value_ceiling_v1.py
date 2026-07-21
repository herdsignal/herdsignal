import pandas as pd
import pytest

from herd.cycle_value_ceiling_v1 import measure_episode
from herd.cycle_value_protocol_v1 import load_protocol


def _frame(future_opens: list[float], split_at: int | None = None) -> pd.DataFrame:
    opens = [100.0, 100.0, *future_opens]
    dates = pd.bdate_range("2020-01-01", periods=len(opens))
    splits = [0.0] * len(opens)
    if split_at is not None:
        splits[split_at] = 2.0
    return pd.DataFrame({
        "Date": dates,
        "Open": opens,
        "Close": opens,
        "Stock Splits": splits,
    })


def test_constrained_ceiling_requires_three_sessions_and_limits_prior_advance():
    protocol = load_protocol()
    future = [105.0, 96.0, 96.0, 96.0] + [100.0] * 122
    result = measure_episode(_frame(future), pd.Timestamp("2020-01-01"), protocol)
    assert result is not None
    assert result["base_constrained_available"] is True
    assert result["base_constrained_time_to_reentry_sessions"] == 2
    assert result["base_constrained_sleeve_share_delta_rate"] > 0.03


def test_advance_above_ten_percent_blocks_late_pullback_window():
    protocol = load_protocol()
    future = [112.0, 95.0, 95.0, 95.0] + [100.0] * 122
    result = measure_episode(_frame(future), pd.Timestamp("2020-01-01"), protocol)
    assert result is not None
    assert result["base_theoretical_available"] is True
    assert result["base_constrained_available"] is False
    assert result["base_constrained_total_position_terminal_uplift"] == 0.0


def test_split_adjustment_does_not_create_false_discount():
    protocol = load_protocol()
    # A 2-for-1 split changes raw price from 100 to 50 without changing equivalent value.
    future = [50.0] * 126
    result = measure_episode(_frame(future, split_at=2), pd.Timestamp("2020-01-01"), protocol)
    assert result is not None
    assert result["base_theoretical_sleeve_share_delta_rate"] < 0.0 or result["base_theoretical_available"] is False
    assert result["base_constrained_available"] is False
