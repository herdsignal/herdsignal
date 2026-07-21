import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from herd.rush_pre_damage_path_audit_v2 import load_protocol, previous_session


def test_feature_cutoff_is_strictly_before_damage_confirmation():
    dates = pd.bdate_range("2024-01-01", periods=5)
    frame = pd.DataFrame({"Date": dates, "Adj Close": np.arange(5)})
    assert previous_session(frame, dates[3]) == dates[2]


def test_protocol_forbids_confirmation_session_input():
    protocol = load_protocol()
    assert protocol["feature_cutoff"] == "PREVIOUS_COMPLETED_TRADING_SESSION_BEFORE_DAMAGE_CONFIRMATION"
    assert "USE_DAMAGE_CONFIRMATION_SESSION_AS_FEATURE_INPUT" in protocol["forbidden"]


def test_registry_records_non_identification_without_action_authority():
    root = Path(__file__).resolve().parents[2]
    registry = json.loads((root / "data/herd/evidence_admission_registry_v9.json").read_text())
    assert registry["decision"]["retained_pre_damage_features"] == []
    assert registry["decision"]["profit_take_evidence_admitted"] is False
    for item in registry["source_artifacts"]:
        assert hashlib.sha256((root / item["path"]).read_bytes()).hexdigest() == item["sha256"]
