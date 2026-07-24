import numpy as np
import pandas as pd

from herd.sec_13f_crowding_incremental_oos_v1 import (
    _predict,
    _transition_events,
    attach_context,
    context_scores,
    fit_single_feature,
)


def test_context_score_requires_breadth_unwind_and_concentration_rise() -> None:
    frame = pd.DataFrame(
        {
            "ticker": ["A", "B", "C"],
            "context_available_date": ["2024-05-16"] * 3,
            "feature_usable": ["true"] * 3,
            "breadth_change_fraction_1q": [-0.2, 0.1, -0.1],
            "top5_concentration_change_1q": [0.2, 0.2, -0.1],
        }
    )
    result = context_scores(frame)
    assert result.loc[0, "crowding_unwind_concentration_score"] > 0
    assert result.loc[1, "crowding_unwind_concentration_score"] == 0
    assert result.loc[2, "crowding_unwind_concentration_score"] == 0


def test_fixed_single_feature_logistic_learns_positive_direction() -> None:
    score = np.array([0.0, 0.1, 0.2, 0.8, 0.9, 1.0])
    target = np.array([0, 0, 0, 1, 1, 1], dtype=float)
    model = fit_single_feature(
        score,
        target,
        penalty=1.0,
        maximum_iterations=100,
        tolerance=1e-10,
    )
    probability = _predict(model, score)
    assert model.coefficient > 0
    assert probability[-1] > probability[0]


def test_transition_selection_keeps_only_breaking_events_with_cooldown(
    tmp_path,
) -> None:
    path = tmp_path / "transition.csv.gz"
    pd.DataFrame(
        {
            "ticker": ["A", "A", "A", "B"],
            "signal_date": [
                "2020-01-03",
                "2020-02-07",
                "2020-08-07",
                "2020-01-03",
            ],
            "last_observed_session": [
                "2020-01-03",
                "2020-02-07",
                "2020-08-07",
                "2020-01-03",
            ],
            "HERD_TRANSITION": [
                "BREAKING",
                "BREAKING",
                "BREAKING",
                "COOLING",
            ],
            "TRANSITION_EVENT": [True, True, True, True],
        }
    ).to_csv(path, index=False, compression="gzip")
    selected = _transition_events(path, cooldown_weeks=26)
    assert selected["ticker"].tolist() == ["A", "A"]
    assert selected["signal_date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2020-01-03",
        "2020-08-07",
    ]


def test_context_join_excludes_missing_ticker_without_date_error() -> None:
    events = pd.DataFrame(
        {
            "ticker": ["MISSING"],
            "signal_date": pd.to_datetime(["2024-06-01"]),
        }
    )
    context = pd.DataFrame(
        {
            "ticker": ["A"],
            "report_period": ["2024-03-31"],
            "context_available_date": pd.to_datetime(["2024-05-16"]),
            "reporting_manager_breadth": [10],
            "breadth_change_fraction_1q": [-0.1],
            "top5_reported_share_concentration": [0.5],
            "top5_concentration_change_1q": [0.1],
            "reported_share_hhi": [0.1],
            "crowding_unwind_concentration_score": [0.8],
            "context_measurement_available": [True],
        }
    )
    result = attach_context(events, context, maximum_age_days=140)
    assert pd.isna(result.loc[0, "context_available_date"])
    assert not bool(result.loc[0, "context_eligible"])
