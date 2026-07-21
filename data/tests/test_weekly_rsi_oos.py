import pandas as pd

from herd.weekly_rsi_oos import _assign_fold, load_protocol


def test_fold_assignment_uses_test_dates_only():
    frame = pd.DataFrame({"date": pd.to_datetime(["2020-01-01", "2021-01-01"])})
    folds = pd.DataFrame({
        "fold_id": ["F1"], "test_start": ["2020-06-01"], "test_end": ["2021-06-01"]
    })
    result = _assign_fold(frame, folds, "date")
    assert result["fold_id"].tolist() == ["F1"]
    assert result["date"].dt.year.tolist() == [2021]


def test_oos_protocol_keeps_action_disabled():
    protocol = load_protocol()
    assert protocol["outcome"]["outcomes_are_labels_only"] is True
    assert "AUTHORIZE_PROFIT_TAKE_BEFORE_INDEPENDENT_OOS_PASS" in protocol["forbidden"]
