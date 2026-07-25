import numpy as np
import pandas as pd
import pytest

from herd.calculator import run
from herd.errors import InsufficientModelHistoryError


def test_short_listing_history_is_ineligible_without_relaxing_model_contract() -> None:
    dates = pd.bdate_range("2025-02-13", periods=360)
    close = np.linspace(40.0, 75.0, len(dates))
    frame = pd.DataFrame(
        {
            "Date": dates.date,
            "Open": close - 0.5,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": np.full(len(dates), 1_000_000),
        }
    )

    with pytest.raises(InsufficientModelHistoryError) as captured:
        run("NEWCO", frame)

    assert captured.value.ticker == "NEWCO"
    assert captured.value.indicators == ("monthly_rsi",)
