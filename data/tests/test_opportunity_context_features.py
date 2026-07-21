import numpy as np
import pandas as pd

from herd.opportunity_context_features import build_market_history, load_contract


def test_market_history_does_not_change_when_future_changes():
    dates = pd.bdate_range("2010-01-01", periods=1000)
    close = np.exp(np.linspace(4, 5, len(dates)))
    frame = pd.DataFrame({"Date": dates, "Adj Close": close})
    first = build_market_history(frame)
    changed = frame.copy()
    changed.loc[900:, "Adj Close"] *= 10
    second = build_market_history(changed)
    pd.testing.assert_frame_equal(first.iloc[:900], second.iloc[:900])


def test_unknown_business_cannot_be_treated_as_zero():
    contract, audit = load_contract()
    assert audit["locked"] is True
    assert contract["missing_policy"]["missing_business"] == "UNKNOWN_NOT_ZERO"
