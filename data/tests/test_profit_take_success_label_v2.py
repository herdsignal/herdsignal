import copy
import json

import pandas as pd
import pytest

from herd.profit_take_success_label_v2 import (
    CONTRACT_PATH,
    ProfitTakeSuccessLabelError,
    REPORT_PATH,
    _fold,
    assign_label,
    validate_contract,
)


def _contract():
    return json.loads(CONTRACT_PATH.read_text())


def test_label_priority_keeps_structural_damage_out_of_rebuy_success():
    assert assign_label(True, "STRUCTURAL_BREAK") == "STRUCTURAL_DAMAGE"
    assert assign_label(True, "TRADABLE_PULLBACK") == "ECONOMIC_REBUY_OPPORTUNITY"
    assert assign_label(False, "CONTINUATION") == "HEALTHY_CONTINUATION"
    assert assign_label(False, "UNRESOLVED") == "NO_ECONOMIC_EDGE"


def test_contract_rejects_future_feature_or_action_authority():
    contract = validate_contract(_contract())
    assert contract["firewall"]["operational_action_ratio"] == 0.0
    changed = copy.deepcopy(contract)
    changed["firewall"]["future_fields_may_enter_features"] = True
    with pytest.raises(ProfitTakeSuccessLabelError):
        validate_contract(changed)


def test_fold_requires_complete_outcome_inside_test_window():
    folds = pd.DataFrame(
        {
            "fold_id": ["F1"],
            "test_start": [pd.Timestamp("2020-01-01")],
            "test_end": [pd.Timestamp("2020-12-31")],
        }
    )
    assert (
        _fold(
            pd.Timestamp("2020-03-01"),
            pd.Timestamp("2020-09-01"),
            folds,
        )
        == "F1"
    )
    assert (
        _fold(
            pd.Timestamp("2020-10-01"),
            pd.Timestamp("2021-01-01"),
            folds,
        )
        is None
    )


def test_checked_in_labels_have_coverage_but_no_action_authority():
    report = json.loads(REPORT_PATH.read_text())
    assert report["coverage_passed"] is True
    assert report["label_counts"]["ECONOMIC_REBUY_OPPORTUNITY"] >= 100
    assert report["label_counts"]["HEALTHY_CONTINUATION"] >= 100
    assert report["direction_evidence_admitted"] is False
    assert report["labels_authorize_actions"] is False
    assert report["operational_action_ratio"] == 0.0
