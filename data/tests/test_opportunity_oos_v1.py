import copy

import pandas as pd
import pytest

from herd.opportunity_oos_v1 import _deduplicate_events, load_registry, validate_registry


def test_duplicate_source_hypotheses_count_once():
    frame = pd.DataFrame([
        {"ticker": "AAPL", "signal_date": "2020-01-31", "label": "CONTINUATION", "fold_id": "F1", "hypothesis_id": "A"},
        {"ticker": "AAPL", "signal_date": "2020-01-31", "label": "CONTINUATION", "fold_id": "F1", "hypothesis_id": "B"},
    ])
    assert len(_deduplicate_events(frame)) == 1


def test_registry_cannot_weaken_fold_gate():
    registry, audit = load_registry()
    assert audit["hypotheses"] == 7
    changed = copy.deepcopy(registry)
    changed["common_test"]["minimum_test_folds"] = 3
    with pytest.raises(ValueError, match="weakened"):
        validate_registry(changed)
