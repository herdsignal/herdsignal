import copy
import json
from tempfile import TemporaryDirectory
from pathlib import Path

import pandas as pd
import pytest

from herd.data_snapshot import load_snapshot
from herd.oos_fold_protocol import (
    OosFoldProtocolError,
    audit_calendar,
    load_protocol,
    validate_protocol,
    load_spy_calendar,
    write_fold_artifacts,
)


DATA_ROOT = Path(__file__).resolve().parents[1]


def test_current_snapshot_allows_price_lane_but_blocks_long_business_lane():
    frames, _ = load_snapshot(DATA_ROOT / "snapshots/yf-10y-20260719")
    calendar = pd.DatetimeIndex(pd.to_datetime(frames["SPY"]["Date"]))

    audit = audit_calendar(calendar)

    assert audit["lanes"]["PRICE_TIMING_6M"]["adoption_ready"] is True
    assert audit["lanes"]["PRICE_TIMING_6M"]["fold_count"] >= 4
    assert audit["lanes"]["BUSINESS_STATE_12M"]["adoption_ready"] is False
    assert audit["lanes"]["BUSINESS_STATE_12M"]["estimated_minimum_calendar_years"] >= 14
    assert audit["lanes"]["BUSINESS_STATE_12M"]["estimated_additional_years_needed"] > 0
    assert audit["all_lanes_adoption_ready"] is False


def test_long_v2_snapshot_unlocks_four_non_overlapping_business_folds():
    calendar = load_spy_calendar(
        DATA_ROOT / "snapshots/yf-long14-actions-sector-20260721"
    )

    audit = audit_calendar(calendar, research_end="2026-07-17")

    business = audit["lanes"]["BUSINESS_STATE_12M"]
    assert business["adoption_ready"] is True
    assert business["fold_count"] >= 4
    assert business["estimated_additional_years_needed"] == 0

    with TemporaryDirectory() as directory:
        output = write_fold_artifacts(Path(directory) / "folds", audit)
        manifest = json.loads(
            (output / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["files"]["BUSINESS_STATE_12M"]["fold_count"] == 4
        assert (output / "business_state_12m.csv").is_file()


def test_protocol_rejects_purge_shorter_than_forward_label():
    protocol = load_protocol()
    changed = copy.deepcopy(protocol)
    changed["lanes"]["PRICE_TIMING_6M"]["purge_days"] = 125

    with pytest.raises(OosFoldProtocolError, match="purge shorter"):
        validate_protocol(changed)


def test_protocol_rejects_overlapping_test_windows():
    protocol = load_protocol()
    changed = copy.deepcopy(protocol)
    changed["lanes"]["BUSINESS_STATE_12M"]["step_years"] = 1

    with pytest.raises(OosFoldProtocolError, match="overlap"):
        validate_protocol(changed)
