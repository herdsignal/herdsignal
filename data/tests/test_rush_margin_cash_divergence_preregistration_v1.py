import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.rush_margin_cash_divergence_preregistration_v1 import (
    REPORT_PATH,
    MarginCashPreregistrationError,
    build_feature_readiness,
    load_contract,
)


def test_preregistration_locks_one_two_family_non_price_hypothesis():
    contract = load_contract()

    assert contract["hypothesis_id"] == "RUSH_MARGIN_CASH_DIVERGENCE_RELATIVE_REBALANCE_V1"
    assert set(contract["economic_hypothesis"]["feature_families"]) == {
        "PIT_MARGIN_TREND",
        "PIT_OPERATING_CASH_FLOW_TREND",
    }
    assert contract["score"]["fit_model"] is False
    assert contract["score"]["hyperparameter_search"] is False
    assert contract["policy"]["reallocation_fraction"] == 0.05
    assert contract["policy"]["destination"] == "SPY"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda c: c["economic_hypothesis"]["feature_families"].append("PRICE_EXTENSION"),
            "economic hypothesis",
        ),
        (
            lambda c: c["score"].update({"candidate_cutoff": "TEST_SCORE_80TH_PERCENTILE"}),
            "fixed interaction score",
        ),
        (
            lambda c: c["policy"].update({"reallocation_fraction": 0.15}),
            "relative-rebalance policy",
        ),
        (
            lambda c: c["oos_design"].update({"purge_sessions": 0}),
            "OOS design",
        ),
        (
            lambda c: c["target_and_gates"].update({"minimum_positive_net_value_rate": 0.5}),
            "adoption gates",
        ),
        (
            lambda c: c["firewall"].update({"oos_target_accessed": True}),
            "firewall",
        ),
    ],
)
def test_preregistration_mutations_fail_closed(tmp_path, mutation, message):
    contract = copy.deepcopy(load_contract())
    mutation(contract)
    path = tmp_path / "mutated.json"
    path.write_text(json.dumps(contract), encoding="utf-8")

    with pytest.raises(MarginCashPreregistrationError, match=message):
        load_contract(path)


def test_feature_readiness_uses_no_outcome_or_policy_value_columns():
    contract = load_contract()
    readiness, summary = build_feature_readiness(contract)

    forbidden = {
        "normalized_net_terminal_wealth_delta",
        "policy_terminal_wealth",
        "hold_terminal_wealth",
        "success_label",
    }
    assert forbidden.isdisjoint(readiness.columns)
    assert summary["feature_ready_events"] == 176
    assert summary["feature_ready_tickers"] == 42
    assert summary["all_readiness_checks_passed"] is True


def test_committed_report_keeps_results_and_actions_closed():
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    assert report["status"] == "PREREGISTERED_READY_FOR_PREHOLDOUT_OOS"
    assert report["score_values_generated"] is False
    assert report["candidate_cutoff_fitted"] is False
    assert report["oos_target_accessed"] is False
    assert report["direction_evidence_admitted"] is False
    assert report["policy_promoted"] is False
    assert report["operational_action"] == "HOLD"
    assert report["operational_action_ratio"] == 0.0
    assert report["blind_holdout_access"] is False
