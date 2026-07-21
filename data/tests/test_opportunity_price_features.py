import numpy as np
import pandas as pd

from herd.opportunity_price_features import calculate_price_features_at, load_contract


def _frame(periods=200):
    dates = pd.bdate_range("2020-01-01", periods=periods)
    close = np.exp(np.linspace(4, 5, periods))
    return pd.DataFrame({
        "Date": dates, "Open": close * 0.999, "High": close * 1.01,
        "Low": close * 0.99, "Close": close, "Adj Close": close,
        "Volume": np.linspace(1_000_000, 2_000_000, periods),
    })


def test_features_use_only_signal_date_or_earlier():
    stock = _frame()
    sector = _frame()
    signal = stock["Date"].iloc[160]
    first = calculate_price_features_at(stock, sector, signal)
    changed = stock.copy()
    changed.loc[changed["Date"] > signal, "Adj Close"] *= 100
    second = calculate_price_features_at(changed, sector, signal)
    assert first == second


def test_feature_contract_marks_overhang_as_proxy():
    contract, audit = load_contract()
    assert audit["locked"] is True
    assert contract["adjustment"]["capital_gain_overhang_is_proxy"] is True
