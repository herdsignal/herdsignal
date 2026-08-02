import copy

import pytest

from herd.failed_hypothesis_map_v1 import FailedHypothesisMapError
from herd.failed_hypothesis_map_v2 import (
    load_failed_hypothesis_map_v2,
    validate_failed_hypothesis_map_v2,
)


def test_v2_appends_latest_failure_without_mutating_v1():
    _, audit = load_failed_hypothesis_map_v2()
    assert audit["parent_experiment_count"] == 10
    assert audit["appended_experiment_count"] == 1
    assert audit["experiment_count"] == 11
    assert audit["adoptable_direction_count"] == 0


def test_v2_cannot_promote_the_appended_failure():
    mapping, _ = load_failed_hypothesis_map_v2()
    changed = copy.deepcopy(mapping)
    changed["appended_experiments"][0]["decision"] = "ADMITTED"
    with pytest.raises(FailedHypothesisMapError, match="incomplete"):
        validate_failed_hypothesis_map_v2(changed)
