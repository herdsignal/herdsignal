import copy
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.rush_margin_cash_divergence_oos_v1 import (
    CONTRACT_PATH,
    REPORT_PATH,
    ROWS_PATH,
    MarginCashOosError,
    _eligible_events,
    _market_sessions,
    build_oos_scores,
    load_contract,
)


def test_oos_contract_locks_leave_one_ticker_out_and_cost_stress():
    contract = load_contract()

    assert (
        contract["training_boundary"]["method"]
        == "EXPANDING_WINDOW_LEAVE_ONE_TEST_TICKER_OUT"
    )
    assert contract["training_boundary"]["same_ticker_history_excluded"] is True
    assert contract["score_execution"]["candidate_quantile"] == 0.9
    assert contract["evaluation"]["costs_bps"] == [10, 25, 50]
    assert contract["firewall"]["operational_action_ratio"] == 0.0


@pytest.mark.parametrize(
    ("section", "key", "value", "message"),
    [
        ("training_boundary", "embargo_sessions", 0, "training boundary"),
        ("score_execution", "candidate_quantile", 0.8, "score execution"),
        ("candidate_budget", "cooldown_market_sessions", 0, "candidate budget"),
        ("evaluation", "costs_bps", [0], "economic evaluation"),
        ("firewall", "operational_action_ratio", 0.05, "firewall"),
    ],
)
def test_oos_contract_mutations_fail_closed(tmp_path, section, key, value, message):
    contract = copy.deepcopy(json.loads(CONTRACT_PATH.read_text(encoding="utf-8")))
    contract[section][key] = value
    path = tmp_path / "mutated.json"
    path.write_text(json.dumps(contract), encoding="utf-8")

    with pytest.raises(MarginCashOosError, match=message):
        load_contract(path)


def test_scoring_stage_has_no_outcome_values_and_fails_early_folds_closed():
    contract = load_contract()
    scores, folds = build_oos_scores(
        contract, _eligible_events(contract), _market_sessions(contract)
    )

    assert "normalized_net_terminal_wealth_delta" not in scores.columns
    assert "missed_upside_cost" not in scores.columns
    by_fold = {row["fold_id"]: row for row in folds}
    assert by_fold["F01"]["scored_events"] == 0
    assert by_fold["F02"]["scored_events"] == 0
    assert by_fold["F03"]["scored_events"] == 12
    assert all(
        pd.to_datetime(scores["feature_accepted_at"], utc=True).dt.date
        < pd.to_datetime(scores["observation_session"]).dt.date
    )


def test_committed_oos_result_rejects_hypothesis_and_keeps_action_closed():
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    rows = pd.read_csv(ROWS_PATH)

    assert report["status"] == "PREHOLDOUT_REJECTED_NO_ACTION_AUTHORITY"
    assert report["scored_events"] == 138
    assert report["candidates"] == 7
    assert report["candidate_tickers"] == 5
    assert report["directional_folds"] == 0
    assert report["median_10bps_net_terminal_wealth_delta"] == pytest.approx(
        -0.0152425095325065
    )
    assert report["positive_10bps_net_value_rate"] == pytest.approx(2 / 7)
    assert report["all_adoption_gates_passed"] is False
    assert sum(report["gate_results"].values()) == 1
    assert rows["candidate"].sum() == 7
    assert report["direction_evidence_admitted"] is False
    assert report["policy_promoted"] is False
    assert report["operational_action"] == "HOLD"
    assert report["operational_action_ratio"] == 0.0
    assert report["blind_holdout_access"] is False
