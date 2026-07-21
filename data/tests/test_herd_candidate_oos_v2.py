import pandas as pd

from herd.herd_candidate_oos_v2 import _assign_folds, _groups


def test_oos_fold_assignment_excludes_training_dates():
    panel = pd.DataFrame({"signal_date":pd.to_datetime(["2019-01-01","2020-06-01"])})
    folds = pd.DataFrame({"fold_id":["F1"],"test_start":["2020-01-01"],"test_end":["2020-12-31"]})
    result = _assign_folds(panel, folds)
    assert result["signal_date"].dt.year.tolist() == [2020]


def test_threshold_is_fitted_from_training_rows_only():
    train = pd.DataFrame({"FEATURE": range(10)})
    test = pd.DataFrame({"FEATURE": [0, 1_000]})
    protocol = {"common": {"control_training_quantile_maximum": .5}}

    treatment, control, threshold = _groups("FEATURE", train, test, .8, protocol)

    assert threshold == train["FEATURE"].quantile(.8)
    assert treatment["FEATURE"].tolist() == [1_000]
    assert control["FEATURE"].tolist() == [0]
