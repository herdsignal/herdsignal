"""라벨 길이에 맞춘 HERD 장기 OOS fold 계약을 생성·감사한다."""

from __future__ import annotations

import argparse
import gzip
import hashlib
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
PROTOCOL_VERSION = "HERD_LONG_HORIZON_OOS_V2"


class OosFoldProtocolError(RuntimeError):
    """장기 OOS 분할이 사전등록 계약을 위반할 때 발생한다."""


def load_spy_calendar(snapshot: Path) -> pd.DatetimeIndex:
    """가격 스냅샷 V1/V2에서 고정 SPY 거래일을 읽는다."""
    root = Path(snapshot)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    version = manifest.get("format_version")
    if version == "herd-price-snapshot-v1":
        frames, _ = load_snapshot(root, tickers=["SPY"])
        dates = frames["SPY"]["Date"]
    elif version == "herd-price-snapshot-v2":
        metadata = manifest.get("files", {}).get("SPY")
        if not metadata:
            raise OosFoldProtocolError("SPY is missing from price snapshot")
        path = root / metadata["path"]
        if not path.is_file():
            raise OosFoldProtocolError("SPY price file is missing")
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            dates = pd.read_csv(stream, usecols=["Date"])["Date"]
    else:
        raise OosFoldProtocolError("unsupported price snapshot format")
    calendar = pd.DatetimeIndex(pd.to_datetime(dates)).sort_values()
    if calendar.empty or calendar.duplicated().any():
        raise OosFoldProtocolError("invalid SPY calendar")
    return calendar


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
        lane = locked["lanes"][lane_id]
        folds = build_lane_folds(
            calendar,
            lane_id,
            protocol=locked,
            research_end=research_end,
        )
        calendar_years = (
            (pd.Timestamp(calendar.max()) - pd.Timestamp(calendar.min())).days
            / 365.2425
        )
        required_years = (
            lane["minimum_train_years"]
            + (lane["purge_days"] + lane["embargo_days"]) / 252.0
            + lane["test_years"]
            + (minimum_folds - 1) * lane["step_years"]
        )
        lane_audits[lane_id] = {
            "fold_count": len(folds),
            "minimum_complete_folds": minimum_folds,
            "adoption_ready": len(folds) >= minimum_folds,
            "calendar_years": round(calendar_years, 2),
            "estimated_minimum_calendar_years": round(required_years, 2),
            "estimated_additional_years_needed": round(
                max(0.0, required_years - calendar_years), 2
            ),
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


def write_fold_artifacts(output: Path, audit: dict) -> Path:
    """lane별 fold CSV와 해시가 포함된 불변 manifest를 기록한다."""
    root = Path(output)
    if root.exists():
        raise OosFoldProtocolError(f"fold artifact exists: {root}")
    root.mkdir(parents=True)
    files = {}
    try:
        for lane_id, lane in audit["lanes"].items():
            path = root / f"{lane_id.lower()}.csv"
            pd.DataFrame(lane["folds"]).to_csv(
                path, index=False, lineterminator="\n"
            )
            files[lane_id] = {
                "path": path.name,
                "fold_count": len(lane["folds"]),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        body = {
            "format_version": "herd-long-oos-fold-artifacts-v1",
            "protocol_version": audit["protocol_version"],
            "calendar_start": audit["calendar_start"],
            "calendar_end": audit["calendar_end"],
            "all_lanes_adoption_ready": audit["all_lanes_adoption_ready"],
            "files": files,
        }
        body["manifest_sha256"] = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        (root / "manifest.json").write_text(
            json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return root
    except Exception:
        import shutil
        shutil.rmtree(root, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--research-end")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    calendar = load_spy_calendar(args.snapshot)
    audit = audit_calendar(calendar, research_end=args.research_end)
    if args.output:
        write_fold_artifacts(args.output, audit)
    print(json.dumps(
        audit,
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
