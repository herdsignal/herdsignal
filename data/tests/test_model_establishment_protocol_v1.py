import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.model_establishment_protocol_v1 import (
    ModelEstablishmentProtocolError,
    load_protocol,
    validate_protocol,
)


def test_integrated_protocol_locks_all_nine_steps_and_zero_action():
    result = validate_protocol(load_protocol())
    assert result["pipeline_steps"] == 9
    assert result["default_action"] == "HOLD"
    assert result["operational_action_ratio"] == 0.0
    assert result["blind_holdout_access"] is False


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("action_boundary", "initial_fraction"), 0.10, "action"),
        (("evaluation", "maximum_pbo"), 0.30, "adoption"),
        (("research_boundaries", "blind_holdout_access"), True, "holdout"),
        (("current_baseline", "current_action_candidate"), "UNVERIFIED", "action"),
    ],
)
def test_protocol_fails_closed_when_a_boundary_is_weakened(path, value, message):
    protocol = copy.deepcopy(load_protocol())
    protocol[path[0]][path[1]] = value
    with pytest.raises(ModelEstablishmentProtocolError, match=message):
        validate_protocol(protocol)
