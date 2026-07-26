from datetime import date

import pandas as pd
import pytest

from scheduler.data_quality_gate import (
    DataQualityGateError,
    validate_operational_price_frame,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame({
        "Date": pd.date_range("2026-07-20", periods=5, freq="B"),
        "Open": [100, 101, 102, 103, 104],
        "High": [101, 102, 103, 104, 105],
        "Low": [99, 100, 101, 102, 103],
        "Close": [100, 101, 102, 103, 104],
        "Volume": [1_000] * 5,
    })


def test_accepts_complete_recent_ohlcv() -> None:
    report = validate_operational_price_frame(
        "AAPL",
        _frame(),
        as_of=date(2026, 7, 26),
    )

    assert report["passed"] is True


def test_rejects_invalid_ohlc_before_calculation_or_save() -> None:
    frame = _frame()
    frame.loc[2, "High"] = 90

    with pytest.raises(DataQualityGateError, match="valid_ohlc_bounds"):
        validate_operational_price_frame(
            "AAPL",
            frame,
            as_of=date(2026, 7, 26),
        )
