import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.fixed_policy_net_value_target_v1 import (
    FixedPolicyTargetError,
    load_contract,
    validate_contract,
)


def test_target_is_locked_without_fabricating_a_policy():
    report = validate_contract(load_contract())

    assert report["primary_target"] == (
        "NET_TERMINAL_WEALTH_DELTA_VERSUS_MATCHED_HOLD"
    )
    assert report["target_generation_allowed"] is False
    assert report["blocked_reason"] == "NO_FIXED_POLICY_REGISTERED"
    assert report["operational_action"] == "HOLD"
    assert report["operational_action_ratio"] == 0.0


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda c: c["matched_hold_benchmark"].update(
                {"same_external_cashflows": False}
            ),
            "matched HOLD",
        ),
        (
            lambda c: c["observation_unit"].update(
                {"execution_earliest": "SIGNAL_CLOSE"}
            ),
            "observation timing",
        ),
        (
            lambda c: c["primary_target"].update(
                {"name": "LARGE_CORRECTION_CLASS"}
            ),
            "primary economic",
        ),
        (
            lambda c: c["firewall"].update(
                {"target_generation_allowed": True}
            ),
            "target firewall",
        ),
    ],
)
def test_target_contract_fails_closed(mutation, message):
    contract = copy.deepcopy(load_contract())
    mutation(contract)

    with pytest.raises(FixedPolicyTargetError, match=message):
        validate_contract(contract)


def test_reentry_cannot_be_selected_inside_the_target_contract():
    contract = copy.deepcopy(load_contract())
    contract["policy_tracks"]["SAME_TICKER_COMPLETED_CYCLE"][
        "reentry_rule"
    ] = "FUTURE_LOW"

    with pytest.raises(FixedPolicyTargetError, match="unregistered policy"):
        validate_contract(contract)


def test_open_trim_is_not_a_completed_cycle_success():
    contract = copy.deepcopy(load_contract())
    contract["policy_tracks"]["SAME_TICKER_COMPLETED_CYCLE"][
        "incomplete_cycle_counts_as_success"
    ] = True

    with pytest.raises(FixedPolicyTargetError, match="unregistered policy"):
        validate_contract(contract)


def test_future_low_prohibition_cannot_be_removed():
    contract = copy.deepcopy(load_contract())
    contract["forbidden"].remove("USE_FUTURE_LOW_AS_EXECUTABLE_REENTRY")

    with pytest.raises(FixedPolicyTargetError, match="forbidden"):
        validate_contract(contract)
