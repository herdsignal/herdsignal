import pandas as pd

from herd.reentry_feature_discovery_v1 import attach_signal_features, load_protocol


def test_only_explicit_signal_time_features_are_attached():
    protocol = load_protocol()
    targets = pd.DataFrame([{
        "ticker": "A", "episode_id": "A1", "signal_date": "2020-01-01",
        "target_label": "REENTRY_WORTHWHILE",
    }])
    panel = pd.DataFrame([{
        "ticker": "A", "episode_id": "A1", "path_label": "STRUCTURAL_BREAK",
        "SECTOR_RS_DAMAGE_DELTA_4W": 1.0,
        "TREND_QUALITY_DELTA_4W": 2.0,
        "PARTICIPATION_WEAKENING_DELTA_4W": 3.0,
        "MARKET_STRESS_DELTA_4W": 4.0,
        "terminal_return_126d": -0.5,
    }])
    result = attach_signal_features(targets, panel, protocol)
    assert "path_label" not in result
    assert "terminal_return_126d" not in result
    assert set(row["id"] for row in protocol["candidate_features"]).issubset(result.columns)
