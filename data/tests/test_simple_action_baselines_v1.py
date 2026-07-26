import json
from pathlib import Path

import numpy as np
import pandas as pd

from herd.simple_action_baselines_v1 import (
    CONTRACT_PATH,
    _expanding_prior_prevalence,
    _metrics,
    build_baselines,
    validate_contract,
)


ROOT = Path(__file__).resolve().parents[2]


def test_contract_locks_baseline_and_action_boundaries() -> None:
    contract = validate_contract(json.loads(CONTRACT_PATH.read_text()))
    assert contract["firewall"]["herd_predictor_training_allowed"] is False
    assert contract["firewall"]["baseline_pass_authorizes_action"] is False
    assert contract["firewall"]["operational_action_ratio"] == 0.0


def test_expanding_prevalence_never_reads_current_fold() -> None:
    contract = json.loads(CONTRACT_PATH.read_text())
    frame = pd.DataFrame(
        {
            "fold_id": ["F1", "F1", "F2", "F2"],
            "actual": [1, 0, 1, 1],
        }
    )
    probability = _expanding_prior_prevalence(frame, contract)
    assert probability[:2].tolist() == [0.5, 0.5]
    assert probability[2:].tolist() == [0.5, 0.5]


def test_metrics_penalize_wrong_certain_policy() -> None:
    actual = np.array([0, 0, 1, 1])
    calibrated = _metrics(actual, np.full(4, 0.5))
    wrong = _metrics(actual, np.array([0.999, 0.999, 0.001, 0.001]))
    assert calibrated["log_loss"] < wrong["log_loss"]
    assert calibrated["brier"] < wrong["brier"]


def test_report_establishes_floors_without_admitting_evidence(tmp_path) -> None:
    report = build_baselines(
        tmp_path / "detail.csv", tmp_path / "report.json"
    )
    assert report["coverage_passed"] is True
    assert report["direction_evidence_admitted"] is False
    assert report["herd_predictor_trained"] is False
    assert report["baseline_results_authorize_action"] is False
    assert report["operational_action_ratio"] == 0.0
    assert set(report["selected_floor_by_universe"]) == {
        "PRIMARY",
        "INDEPENDENT_CURRENT_CONSTITUENTS",
    }
