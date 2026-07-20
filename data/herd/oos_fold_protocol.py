"""라벨 길이에 맞춘 HERD 장기 OOS fold 계약을 생성·감사한다."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from herd.data_snapshot import load_snapshot
from herd.walk_forward_artifacts import (
    Fold,
    WalkForwardConfig,
    build_anchored_folds,
)


PROTOCOL_PATH = Path(__file__).with_name("oos_fold_protocol.json")
PROTOCOL_VERSION = "HERD_LONG_HORIZON_OOS_V1"


class OosFoldProtocolError(RuntimeError):
    """장기 OOS 분할이 사전등록 계약을 위반할 때 발생한다."""


def load_protocol(path: Path = PROTOCOL_PATH) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    validate_protocol(protocol)
    return protocol


def validate_protocol(protocol: dict) -> None:
    if (
        protocol.get("protocol_version") != PROTOCOL_VERSION
        or protocol.get("status") != "LOCKED_BEFORE_NEW_HYPOTHESIS_RESULTS"
        or protocol.get("calendar_source") != "SPY_TRADING_DAYS"
        or protocol.get("minimum_complete_folds", 0) < 4
    ):
        raise OosFoldProtocolError("OOS fold protocol is not locked")

    lanes = protocol.get("lanes", {})
    if set(lanes) != {"PRICE_TIMING_6M", "BUSINESS_STATE_12M"}:
        raise OosFoldProtocolError("required validation lanes changed")
    for lane_id, lane in lanes.items():
        if lane["purge_days"] < lane["maximum_label_horizon_trading_days"]:
            raise OosFoldProtocolError(f"purge shorter than label: {lane_id}")
        if lane["step_years"] < lane["test_years"]:
            raise OosFoldProtocolError(f"test folds overlap: {lane_id}")
        if lane["embargo_days"] < 0:
            raise OosFoldProtocolError(f"negative embargo: {lane_id}")

    event_rules = protocol.get("event_rules", {})
    if (
        event_rules.get("outcome_must_end_inside_test_fold") is not True
        or event_rules.get("overlapping_test_windows") is not False
        or event_rules.get("cross_fold_event_reuse") is not False
        or event_rules.get("insufficient_fold_action")
        != "BLOCK_HYPOTHESIS_ADOPTION"
    ):
        raise OosFoldProtocolError("event independence rules are incomplete")


def _config(lane: dict, research_end: str | None) -> WalkForwardConfig:
    return WalkForwardConfig(
        min_train_years=lane["minimum_train_years"],
        test_years=lane["test_years"],
        step_years=lane["step_years"],
        purge_days=lane["purge_days"],
        embargo_days=lane["embargo_days"],
        research_end=research_end,
    )


def build_lane_folds(
    calendar: pd.DatetimeIndex,
    lane_id: str,
    *,
    protocol: dict | None = None,
    research_end: str | None = None,
) -> list[Fold]:
    locked = protocol or load_protocol()
    if lane_id not in locked["lanes"]:
        raise OosFoldProtocolError(f"unknown OOS lane: {lane_id}")
    folds = build_anchored_folds(
        calendar,
        _config(locked["lanes"][lane_id], research_end),
    )
    for previous, current in zip(folds, folds[1:]):
        if pd.Timestamp(current.test_start) <= pd.Timestamp(previous.test_end):
            raise OosFoldProtocolError(f"overlapping test folds: {lane_id}")
    return folds


def audit_calendar(
    calendar: pd.DatetimeIndex,
    *,
    protocol: dict | None = None,
    research_end: str | None = None,
) -> dict:
    locked = protocol or load_protocol()
    minimum_folds = locked["minimum_complete_folds"]
    lane_audits = {}
    for lane_id in locked["lanes"]:
        folds = build_lane_folds(
            calendar,
            lane_id,
            protocol=locked,
            research_end=research_end,
        )
        lane_audits[lane_id] = {
            "fold_count": len(folds),
            "minimum_complete_folds": minimum_folds,
            "adoption_ready": len(folds) >= minimum_folds,
            "folds": [asdict(fold) for fold in folds],
        }
    return {
        "protocol_version": PROTOCOL_VERSION,
        "calendar_start": pd.Timestamp(calendar.min()).date().isoformat(),
        "calendar_end": pd.Timestamp(calendar.max()).date().isoformat(),
        "lanes": lane_audits,
        "all_lanes_adoption_ready": all(
            audit["adoption_ready"] for audit in lane_audits.values()
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--research-end")
    args = parser.parse_args()
    frames, _ = load_snapshot(args.snapshot)
    calendar = pd.DatetimeIndex(pd.to_datetime(frames["SPY"]["Date"]))
    print(json.dumps(
        audit_calendar(calendar, research_end=args.research_end),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
