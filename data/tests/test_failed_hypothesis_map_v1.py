import copy

import pytest

from herd.failed_hypothesis_map_v1 import (
    FailedHypothesisMapError,
    load_failed_hypothesis_map,
    validate_failed_hypothesis_map,
)


def test_all_failed_hypotheses_are_pinned_with_retry_boundaries():
    _, audit = load_failed_hypothesis_map()
    assert audit["experiment_count"] == 10
    assert audit["rejected_count"] == 10
    assert audit["adoptable_direction_count"] == 0
    assert audit["duplicate_experiment_keys"] == 0
    assert audit["source_reports_verified"] == 10


def test_same_sample_retuning_cannot_be_enabled():
    mapping, _ = load_failed_hypothesis_map()
    changed = copy.deepcopy(mapping)
    changed["global_rules"]["same_sample_threshold_retuning_forbidden"] = False
    with pytest.raises(FailedHypothesisMapError, match="boundary weakened"):
        validate_failed_hypothesis_map(changed)


def test_rejected_experiment_cannot_be_relabelled_as_admitted():
    mapping, _ = load_failed_hypothesis_map()
    changed = copy.deepcopy(mapping)
    changed["experiments"][0]["decision"] = "ADMITTED"
    with pytest.raises(FailedHypothesisMapError, match="incomplete rejection"):
        validate_failed_hypothesis_map(changed)
