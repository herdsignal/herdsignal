import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.vnext_preholdout_evaluation_v1 import (
    VNextPreholdoutError,
    _binary_metrics,
    _fold_data,
    load_protocol,
    validate_protocol,
)


def test_protocol_locks_purge_and_zero_action_authority():
    audit = validate_protocol(load_protocol())
    assert audit["outcome_purge"] is True
    assert audit["historical_role"] == "PRE_HOLDOUT_ONLY"
    assert audit["operational_action_ratio"] == 0.0


def test_fold_purges_train_rows_whose_outcome_overlaps_test():
    panel = pd.DataFrame(
        {
            "signal_date": pd.to_datetime(
                ["2015-01-01", "2015-12-01", "2016-06-01"]
            ),
            "vnext_outcome_end": pd.to_datetime(
                ["2015-07-01", "2016-05-01", "2016-12-01"]
            ),
            "target": [0.0, 1.0, 1.0],
        }
    )
    fold = {
        "train_end": "2015-12-31",
        "test_start": "2016-01-01",
        "test_end": "2016-12-31",
    }
    train, test = _fold_data(panel, fold)
    assert len(train) == 1
    assert len(test) == 1


def test_probability_metrics_reward_correct_ranking():
    metrics = _binary_metrics(
        np.array([0, 0, 1, 1]),
        np.array([0.1, 0.2, 0.8, 0.9]),
        threshold=0.5,
    )
    assert metrics["roc_auc"] == 1.0
    assert metrics["balanced_accuracy"] == 1.0
    assert metrics["brier"] < 0.05


def test_protocol_cannot_relabel_historical_data_as_blind():
    protocol = json.loads(json.dumps(load_protocol()))
    protocol["promotion_boundary"]["historical_result_is_preholdout_only"] = False
    with pytest.raises(VNextPreholdoutError, match="promotion"):
        validate_protocol(protocol)
