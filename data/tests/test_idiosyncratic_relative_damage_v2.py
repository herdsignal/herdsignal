import numpy as np
import pandas as pd

from herd.idiosyncratic_relative_damage_v2 import features_as_of, load_protocol


def _frame(values):
    dates = pd.bdate_range("2020-01-01", periods=len(values))
    values = np.asarray(values, dtype=float)
    return pd.DataFrame({"Date": dates, "Adj Close": values})


def test_future_prices_do_not_change_as_of_measurement():
    protocol = load_protocol()
    base = np.linspace(100, 150, 180)
    first = _frame(np.r_[base, np.linspace(151, 180, 20)])
    second = _frame(np.r_[base, np.linspace(149, 80, 20)])
    benchmark = _frame(np.linspace(100, 130, 200))
    as_of = first.iloc[179]["Date"]
    assert features_as_of(first, benchmark, benchmark, as_of, protocol) == features_as_of(second, benchmark, benchmark, as_of, protocol)


def test_relative_damage_cannot_create_sell_alone():
    assert "RELATIVE_DAMAGE_ALONE_CREATES_SELL" in load_protocol()["forbidden"]
