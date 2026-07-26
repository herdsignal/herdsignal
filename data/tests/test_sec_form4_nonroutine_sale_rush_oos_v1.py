import json

import pandas as pd

from herd.sec_form4_nonroutine_sale_rush_oos_v1 import (
    REPORT_PATH,
    _attach_exposure,
    _fold,
    _risk_difference,
)


def test_exposure_requires_two_distinct_owners_strictly_before_signal():
    entries = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "sector_etf": "XLK",
                "universe_role": "PRIMARY",
                "signal_date": pd.Timestamp("2026-05-31"),
                "HERD_STATE": 80.0,
            }
        ]
    )
    sales = pd.DataFrame(
        [
            {"filingDate": pd.Timestamp("2026-05-02"), "reportingOwnerCik": "1"},
            {"filingDate": pd.Timestamp("2026-05-20"), "reportingOwnerCik": "2"},
            {"filingDate": pd.Timestamp("2026-05-31"), "reportingOwnerCik": "3"},
        ]
    )
    result = _attach_exposure(entries, {"AAA": sales}, 30, 2)
    assert result.iloc[0]["distinct_sale_owners_30d"] == 2
    assert bool(result.iloc[0]["exposed"]) is True


def test_fold_rejects_outcome_crossing_fold_end():
    folds = [{"id": "F1", "start": "2024-01-01", "end": "2024-12-31"}]
    assert _fold(pd.Timestamp("2024-10-01"), pd.Timestamp("2024-12-30"), folds) == "F1"
    assert _fold(pd.Timestamp("2024-10-01"), pd.Timestamp("2025-01-02"), folds) is None


def test_risk_difference_uses_exposed_minus_control():
    frame = pd.DataFrame(
        {"exposed": [True, True, False, False], "adverse_path": [True, False, False, False]}
    )
    difference, ratio = _risk_difference(frame)
    assert difference == 0.5
    assert ratio == float("inf")


def test_frozen_result_cannot_authorize_action():
    report = json.loads(REPORT_PATH.read_text())
    assert report["passed"] is False
    assert report["adoption_allowed"] is False
    assert report["operational_action_ratio"] == 0.0
    assert all(
        fold["direction_matches_hypothesis"] is False
        for fold in report["folds"]
    )
