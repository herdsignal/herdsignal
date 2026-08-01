import copy
import json

import pytest

from herd.action_cycle_architecture_v2 import (
    CONTRACT_PATH,
    ActionCycleArchitectureError,
    build_report,
    validate_contract,
)


def _contract():
    return json.loads(CONTRACT_PATH.read_text())


def test_contract_separates_observation_from_predictive_action():
    contract = validate_contract(_contract())
    lanes = {item["id"]: item for item in contract["productLanes"]}
    assert lanes["OBSERVATION_AND_POLICY_REVIEW"]["mayAuthorizeTrade"] is False
    assert lanes["PREDICTIVE_ACTION_CYCLE"][
        "availableBeforeDirectionEvidence"
    ] is False


def test_contract_separates_reentry_and_new_entry():
    contract = validate_contract(_contract())
    assert contract["actionLanes"]["matchedCashReentry"][
        "requiresPriorSaleCash"
    ] is True
    assert contract["actionLanes"]["newEntry"]["mayReuseReentryRule"] is False


def test_contract_rejects_action_authority_or_external_cash_weakening():
    changed = copy.deepcopy(_contract())
    changed["currentBoundary"]["operationalAction"] = "REDUCE"
    with pytest.raises(ActionCycleArchitectureError):
        validate_contract(changed)

    changed = copy.deepcopy(_contract())
    changed["cycleStateMachine"]["completedRequires"].remove("NO_EXTERNAL_CASH")
    with pytest.raises(ActionCycleArchitectureError):
        validate_contract(changed)


def test_checked_in_evidence_defines_target_but_does_not_admit_candidate(tmp_path):
    report = build_report(tmp_path / "report.json")
    assert report["foundationReady"] is True
    assert report["directionTargetDefined"] is True
    assert report["newCandidateReady"] is False
    assert report["directionResearchReady"] is False
    assert report["profitTakeReviewAllowed"] is False
    assert report["matchedCashReentryReviewAllowed"] is False
    assert report["operationalAction"] == "HOLD"
    assert report["operationalActionRatio"] == 0.0
