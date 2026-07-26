import copy
import hashlib
import json

import pytest

from herd.rush_event_dataset_v2 import (
    PROTOCOL_PATH,
    RushEventDatasetV2Error,
    build_dataset,
)


def test_rush_v2_dataset_is_reproducible_and_time_safe(tmp_path):
    report = build_dataset(
        json.loads(PROTOCOL_PATH.read_text()),
        tmp_path / "events.csv",
        tmp_path / "report.json",
    )
    assert report["rows"] == 1998
    assert report["tickers"] == 381
    assert report["path_labels"]["STRUCTURAL_BREAK"] == 192
    assert report["missing_pre_confirmation_feature_cells"] == 13
    committed = json.loads(
        (PROTOCOL_PATH.parents[1] / "reports/rush_event_dataset_v2.json").read_text()
    )
    assert hashlib.sha256((tmp_path / "events.csv").read_bytes()).hexdigest() == committed[
        "dataset_sha256"
    ]
    assert report["survivorship_safe"] is False
    assert report["operational_action_ratio"] == 0.0


def test_rush_v2_cannot_gain_action_authority(tmp_path):
    protocol = json.loads(PROTOCOL_PATH.read_text())
    changed = copy.deepcopy(protocol)
    changed["authority"]["profit_take"] = True
    with pytest.raises(RushEventDatasetV2Error, match="authority"):
        build_dataset(changed, tmp_path / "events.csv", tmp_path / "report.json")
