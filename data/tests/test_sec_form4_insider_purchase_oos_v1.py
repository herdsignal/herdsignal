import pandas as pd

from herd.sec_form4_insider_purchase_oos_v1 import (
    attach_episode_feature,
    evaluate_panel,
)


def _protocol():
    return {
        "population": {
            "adverse_path_labels": ["LARGE_PULLBACK", "STRUCTURAL_BREAK"],
            "non_adverse_path_labels": ["CONTINUATION", "TEMPORARY_PULLBACK"],
        },
        "feature_definition": {"lookback_calendar_days": 90},
        "oos_folds": [{
            "id": "F1",
            "start": "2020-01-01",
            "end": "2020-12-31",
        }],
        "adoption_gate": {
            "minimum_resolved_episodes": 1,
            "minimum_feature_positive_episodes": 1,
            "minimum_feature_positive_tickers": 1,
            "minimum_folds_with_at_least_10_positive_episodes": 0,
            "minimum_direction_consistent_folds": 1,
            "maximum_pooled_adverse_risk_difference": -0.05,
            "maximum_pooled_relative_risk": 0.85,
            "maximum_ticker_cluster_bootstrap_95_upper_risk_difference": 1.0,
        },
    }


def test_feature_uses_only_filings_strictly_before_signal():
    episodes = pd.DataFrame([
        {
            "ticker": "AAA",
            "episode_id": "before",
            "signal_date": "2020-04-15",
            "path_label": "CONTINUATION",
        },
        {
            "ticker": "AAA",
            "episode_id": "same-day",
            "signal_date": "2020-04-01",
            "path_label": "LARGE_PULLBACK",
        },
    ])
    events = pd.DataFrame([{
        "issuerCik": "0000000001",
        "reportingOwnerCik": "0000000002",
        "filingDate": "2020-04-01",
        "routineStatus": "NON_ROUTINE_CANDIDATE",
    }])
    universe = pd.DataFrame([{
        "ticker": "AAA",
        "cik": "1",
        "eligible": True,
    }])
    panel = attach_episode_feature(episodes, events, universe, _protocol())
    values = panel.set_index("episode_id")["purchaseSupport90d"].to_dict()
    assert values["before"] == 1
    assert values["same-day"] == 0


def test_evaluation_requires_protective_direction():
    panel = pd.DataFrame([
        {
            "ticker": "A",
            "foldId": "F1",
            "purchaseSupport90d": 1,
            "adversePath": 0,
        },
        {
            "ticker": "B",
            "foldId": "F1",
            "purchaseSupport90d": 0,
            "adversePath": 1,
        },
        {
            "ticker": "C",
            "foldId": "F1",
            "purchaseSupport90d": 0,
            "adversePath": 0,
        },
    ])
    _, report = evaluate_panel(panel, _protocol())
    assert report["pooled_adverse_risk_difference"] == -0.5
    assert report["checks"]["maximum_pooled_adverse_risk_difference"]
    assert report["direction_consistent_folds"] == 1
