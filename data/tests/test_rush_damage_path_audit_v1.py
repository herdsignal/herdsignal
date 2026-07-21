import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from herd.rush_damage_path_audit_v1 import classify_path, load_protocol, observable_features


def _frame(close, volume=None):
    values = np.asarray(close, dtype=float)
    dates = pd.bdate_range("2020-01-01", periods=len(values))
    volume = np.ones(len(values)) * 100 if volume is None else np.asarray(volume, dtype=float)
    return pd.DataFrame({"Date": dates, "Open": values, "Close": values, "Adj Close": values, "Volume": volume})


def test_path_labels_are_mutually_exclusive_and_use_post_damage_only_as_outcome():
    protocol = load_protocol()
    history = np.linspace(50, 100, 100)
    structural = _frame(np.r_[history, np.linspace(99, 70, 63)])
    resumed = _frame(np.r_[history, np.linspace(101, 120, 63)])
    damage_date = pd.Timestamp(structural.iloc[99]["Date"])
    assert classify_path(structural, damage_date, protocol)["path_label"] == "STRUCTURAL_BREAK"
    assert classify_path(resumed, damage_date, protocol)["path_label"] == "RESUMED_UPTREND"


def test_observable_features_do_not_change_when_future_prices_change():
    past = np.linspace(80, 100, 100)
    first = _frame(np.r_[past, np.linspace(101, 120, 63)])
    second = _frame(np.r_[past, np.linspace(99, 60, 63)])
    benchmark = _frame(np.linspace(80, 105, 163))
    damage_date = pd.Timestamp(first.iloc[99]["Date"])
    assert observable_features(first, benchmark, benchmark, damage_date) == observable_features(second, benchmark, benchmark, damage_date)


def test_protocol_blocks_same_sample_profit_take_authority():
    protocol = load_protocol()
    assert protocol["interpretation"]["same_sample_action_authority"] is False
    assert "AUTHORIZE_PROFIT_TAKE_FROM_THIS_AUDIT" in protocol["forbidden"]


def test_registry_pins_diagnostic_without_granting_action_authority():
    root = Path(__file__).resolve().parents[2]
    registry = json.loads((root / "data/herd/evidence_admission_registry_v8.json").read_text())
    assert registry["decision"]["profit_take_evidence_admitted"] is False
    assert registry["decision"]["retained_discovery_leads"] == [
        "downside_acceleration_5_21", "realized_vol_expansion_20_63"
    ]
    for item in registry["source_artifacts"]:
        assert hashlib.sha256((root / item["path"]).read_bytes()).hexdigest() == item["sha256"]
