import hashlib
import json
from pathlib import Path

import pandas as pd

from herd.immediate_healthy_add_baseline_v1 import build_results, load_protocol


def test_protocol_is_baseline_not_action_authority():
    protocol = load_protocol()
    assert protocol["interpretation"]["same_sample_baseline_only"] is True
    assert protocol["interpretation"]["pass_does_not_authorize_add_buy"] is True
    assert protocol["portfolio"]["sleeve_ratio"] == 0.05


def test_same_month_business_state_is_rejected():
    protocol = load_protocol()
    source = pd.DataFrame([{
        "ticker": "A", "signal_date": "2020-02-14", "fold_id": "F01",
        "business_state": "PASS", "business_month_end": "2020-02-01", "outcome_end": "2020-08-14",
    }])
    try:
        build_results(source, {}, protocol)
    except ValueError as error:
        assert "same-month" in str(error)
    else:
        raise AssertionError("same-month business state must fail closed")


def test_cash_and_scheduled_comparators_are_both_primary():
    protocol = load_protocol()
    assert protocol["primary_comparisons"] == ["IMMEDIATE_MINUS_CASH", "IMMEDIATE_MINUS_SCHEDULED_21"]
    assert protocol["baseline_gate"]["required_comparisons_passed"] == 2
    assert protocol["inference"]["required_units"] == ["TICKER_MEAN", "SIGNAL_MONTH_MEAN"]


def test_admission_registry_pins_non_admission():
    root = Path(__file__).resolve().parents[2]
    registry = json.loads((root / "data/herd/evidence_admission_registry_v6.json").read_text())
    assert registry["decision"]["timing_evidence_admitted"] is False
    assert registry["decision"]["scheduled_21_comparison_passed"] is False
    for item in registry["source_artifacts"]:
        assert hashlib.sha256((root / item["path"]).read_bytes()).hexdigest() == item["sha256"]
