import copy

import pandas as pd
import pytest

from herd.data_snapshot import load_snapshot
from herd.oos_fold_protocol import (
    OosFoldProtocolError,
    audit_calendar,
    load_protocol,
    validate_protocol,
)


def test_current_snapshot_allows_price_lane_but_blocks_long_business_lane():
    frames, _ = load_snapshot("snapshots/yf-10y-20260719")
    calendar = pd.DatetimeIndex(pd.to_datetime(frames["SPY"]["Date"]))

    audit = audit_calendar(calendar)

    assert audit["lanes"]["PRICE_TIMING_6M"]["adoption_ready"] is True
    assert audit["lanes"]["PRICE_TIMING_6M"]["fold_count"] >= 4
    assert audit["lanes"]["BUSINESS_STATE_12M"]["adoption_ready"] is False
    assert audit["all_lanes_adoption_ready"] is False


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
