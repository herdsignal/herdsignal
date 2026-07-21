import numpy as np
import pandas as pd

from herd.opportunity_cycle_path import diagnose_path, load_target


def _series(future: list[float]) -> tuple[pd.Series, pd.Timestamp]:
    history = list(np.linspace(90, 100, 80))
    values = history + future
    index = pd.bdate_range("2020-01-01", periods=len(values))
    return pd.Series(values, index=index), index[len(history) - 1]


def test_continuation_and_pullback_are_not_the_same_target():
    target, _ = load_target()
    continuation, date = _series(list(np.linspace(101, 125, 126)))
    pullback_path = list(np.linspace(99, 92, 30)) + list(np.linspace(92, 106, 96))
    pullback, pullback_date = _series(pullback_path)
    assert diagnose_path(continuation, date, target)["label"] == "CONTINUATION"
    assert diagnose_path(pullback, pullback_date, target)["label"] == "TRADABLE_PULLBACK"


def test_oracle_path_is_explicitly_non_executable():
    target, audit = load_target()
    assert audit["locked"] is True
    assert target["interpretation"]["oracle_reentry_is_not_executable"] is True
    assert target["interpretation"]["labels_do_not_authorize_actions"] is True
