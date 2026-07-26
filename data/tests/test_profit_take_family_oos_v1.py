import json

import numpy as np

from herd.profit_take_family_oos_v1 import (
    CONTRACT_PATH,
    _fit_logistic,
    _predict,
    build_evaluation,
    validate_contract,
)


def test_contract_forbids_combination_and_action() -> None:
    contract = validate_contract(json.loads(CONTRACT_PATH.read_text()))
    boundary = contract["research_boundary"]
    assert boundary["family_combination_allowed"] is False
    assert boundary["same_sample_threshold_search"] is False
    assert boundary["operational_action_ratio"] == 0.0
    assert contract["estimator"]["dropping_missing_events_allowed"] is False


def test_univariate_logistic_learns_direction() -> None:
    feature = np.array([-2, -1, -0.5, 0.5, 1, 2], dtype=float)
    actual = np.array([0, 0, 0, 1, 1, 1], dtype=float)
    beta = _fit_logistic(feature, actual, penalty=1.0)
    prediction = _predict(np.array([-1.0, 1.0]), beta)
    assert prediction[0] < prediction[1]


def test_evaluation_fail_closes_or_admits_only_named_families(tmp_path) -> None:
    report = build_evaluation(
        tmp_path / "detail.csv", tmp_path / "report.json"
    )
    contract = json.loads(CONTRACT_PATH.read_text())
    assert set(report["admitted_families"]).issubset(
        set(contract["families_tested_independently"])
    )
    assert report["completed_cycle_allowed"] is False
    assert report["blind_holdout_access"] is False
    assert report["operational_action_ratio"] == 0.0
    for families in report["universe_results"].values():
        for result in families.values():
            assert result["events_dropped_for_missing_feature"] == 0
            assert np.isfinite(result["candidate_log_loss"])
