import pandas as pd

from herd.rush_path_comparison_v2 import _rank_biserial, attach_features, load_protocol


def test_rank_biserial_direction_is_positive_when_treatment_is_higher():
    effect, _ = _rank_biserial(pd.Series([8, 9, 10]), pd.Series([1, 2, 3]))
    assert effect == 1.0


def test_feature_attachment_uses_exact_ticker_date_key():
    paths = pd.DataFrame({"ticker":["A"], "signal_date":["2020-01-03"], "path_label":["CONTINUATION"]})
    features = pd.DataFrame({"ticker":["A"], "signal_date":["2020-01-03"], "FEATURE":[1.5]})
    result = attach_features(paths, features)
    assert result["FEATURE"].tolist() == [1.5]


def test_protocol_keeps_confirmation_period_out_of_selection():
    protocol = load_protocol()
    assert protocol["discovery_end"] < protocol["confirmation_start"]
