import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.vnext_joint_model_v1 import (
    VNextJointModelError,
    _attach_business_state,
    fit_joint_model,
    load_protocol,
    predict_joint_probability,
    validate_protocol,
)


def _synthetic() -> pd.DataFrame:
    rng = np.random.default_rng(17)
    rows = 300
    trend = rng.normal(size=rows)
    peer = rng.normal(size=rows)
    risk = -trend * peer + rng.normal(scale=0.4, size=rows)
    return pd.DataFrame(
        {
            "SECTOR_RS_DAMAGE_DELTA_4W": rng.normal(size=rows),
            "MARKET_STRESS_DELTA_4W": rng.normal(size=rows),
            "TREND_QUALITY_DELTA_4W": trend,
            "DECELERATION_DELTA_4W": rng.normal(size=rows),
            "HIGH_FAILURE_DELTA_4W": rng.normal(size=rows),
            "PEER_HIGH_EXIT_SHARE_DELTA_4W": peer,
            "PEER_ADVANCE_BREADTH_DELTA_4W": rng.normal(size=rows),
            "BUSINESS_VETO": rng.integers(0, 2, size=rows),
            "BUSINESS_UNKNOWN": np.zeros(rows),
            "target": (risk > 0).astype(float),
        }
    )


def test_protocol_locks_one_interaction_and_no_search():
    report = validate_protocol(load_protocol())
    assert report["single_interaction"] == "STOCK_TREND_DAMAGE_X_PEER_HIGH_EXIT"
    assert report["l2_penalty"] == 1.0
    assert report["operational_action_authority"] is False


def test_fixed_model_learns_joint_risk_without_threshold_search():
    frame = _synthetic()
    model = fit_joint_model(frame.iloc[:220])
    probability = predict_joint_probability(model, frame.iloc[220:])
    assert np.isfinite(probability).all()
    assert ((probability >= 0) & (probability <= 1)).all()
    predicted = probability >= 0.5
    actual = frame.iloc[220:]["target"].astype(bool).to_numpy()
    assert (predicted == actual).mean() > 0.70


def test_block_ablation_removes_parent_interaction():
    frame = _synthetic()
    model = fit_joint_model(frame, omitted_block="PEER_PARTICIPATION")
    assert "PEER_HIGH_EXIT_SHARE_DELTA_4W" not in model.feature_names
    assert "STOCK_TREND_DAMAGE_X_PEER_HIGH_EXIT" not in model.feature_names


def test_interaction_can_be_removed_only_for_ablation():
    model = fit_joint_model(_synthetic(), include_interaction=False)
    assert "STOCK_TREND_DAMAGE_X_PEER_HIGH_EXIT" not in model.feature_names
    assert "PEER_HIGH_EXIT_SHARE_DELTA_4W" in model.feature_names


def test_training_requires_both_classes():
    frame = _synthetic()
    frame["target"] = 1.0
    with pytest.raises(VNextJointModelError, match="both"):
        fit_joint_model(frame)


def test_training_rejects_all_missing_feature():
    frame = _synthetic()
    frame["MARKET_STRESS_DELTA_4W"] = np.nan
    with pytest.raises(VNextJointModelError, match="all-missing"):
        fit_joint_model(frame)


def test_protocol_rejects_hyperparameter_search():
    protocol = json.loads(json.dumps(load_protocol()))
    protocol["model"]["hyperparameter_search"] = True
    with pytest.raises(VNextJointModelError, match="complexity"):
        validate_protocol(protocol)


def test_business_month_end_state_is_not_available_on_same_day(tmp_path):
    business = pd.DataFrame(
        {
            "ticker": ["A", "A"],
            "month_end": ["2025-01-31", "2025-02-28"],
            "guard_state": ["PASS", "VETO"],
            "latest_fact_accepted_at": [
                "2025-01-30T20:00:00+00:00",
                "2025-02-28T22:00:00+00:00",
            ],
            "flag_count": [0, 4],
        }
    )
    path = tmp_path / "business.csv"
    business.to_csv(path, index=False)
    events = pd.DataFrame(
        {
            "ticker": ["A", "A"],
            "signal_date": pd.to_datetime(["2025-02-28", "2025-03-03"]),
        }
    )

    attached = _attach_business_state(events, path)

    assert attached.loc[0, "guard_state"] == "PASS"
    assert attached.loc[1, "guard_state"] == "VETO"
