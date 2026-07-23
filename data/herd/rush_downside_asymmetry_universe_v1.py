"""기존 1,998건과 티커가 겹치지 않는 Rush 하방 비대칭 OOS 표본을 잠근다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from herd.long_price_snapshot import verify_snapshot


PROTOCOL_PATH = Path(__file__).with_name("rush_downside_asymmetry_protocol_v1.json")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_protocol(path: Path = PROTOCOL_PATH) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_OOS_MEASUREMENT":
        raise ValueError("protocol must be locked before OOS measurement")
    policy = protocol.get("policy", {})
    if policy.get("threshold_tuning_after_results") is not False:
        raise ValueError("post-result threshold tuning must be forbidden")
    if policy.get("operational_action_authority") is not False:
        raise ValueError("research protocol cannot authorize actions")
    return protocol


def build_universe(
    audit_path: Path,
    discovery_events_path: Path,
    snapshot_path: Path,
    protocol_path: Path = PROTOCOL_PATH,
) -> tuple[pd.DataFrame, dict]:
    protocol = load_protocol(protocol_path)
    snapshot = verify_snapshot(snapshot_path)
    audit = pd.read_csv(audit_path)
    discovery = pd.read_csv(discovery_events_path, usecols=["ticker"])
    excluded = set(discovery["ticker"].astype(str))
    minimum_rows = int(protocol["sample"]["minimum_price_sessions"])
    rows = audit[
        ~audit["ticker"].isin(excluded)
        & audit["sector_etf"].notna()
        & (audit["price_rows"] >= minimum_rows)
    ].copy()
    rows = rows.sort_values("ticker").reset_index(drop=True)
    rows["sample_role"] = "INDEPENDENT_TICKER_OOS"
    rows["survivorship_safe"] = False
    selected = set(rows["ticker"])
    if selected & excluded:
        raise AssertionError("discovery and OOS tickers overlap")
    missing_snapshot = selected - set(snapshot["files"])
    if missing_snapshot:
        raise ValueError(f"snapshot missing selected tickers: {sorted(missing_snapshot)}")
    sector_count = int(rows["sector_etf"].nunique())
    report = {
        "report_version": "HERD_RUSH_DOWNSIDE_ASYMMETRY_UNIVERSE_V1",
        "status": "LOCKED_OOS_UNIVERSE" if (
            len(rows) >= protocol["sample"]["minimum_tickers"]
            and sector_count >= protocol["sample"]["required_sector_count"]
        ) else "OOS_UNIVERSE_GATE_FAILED",
        "protocol_sha256": _sha256(protocol_path),
        "audit_sha256": _sha256(audit_path),
        "discovery_events_sha256": _sha256(discovery_events_path),
        "snapshot_id": snapshot["snapshot_id"],
        "snapshot_sha256": snapshot["snapshot_sha256"],
        "discovery_tickers_excluded": len(excluded),
        "selected_tickers": len(rows),
        "sector_count": sector_count,
        "ticker_overlap_count": len(selected & excluded),
        "minimum_price_sessions": minimum_rows,
        "ticker_list": rows["ticker"].tolist(),
        "claim_boundary": protocol["sample"]["claim_boundary"],
        "survivorship_safe": False,
        "operational_action_authority": False,
        "blind_holdout_access": False
    }
    return rows, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--discovery-events", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL_PATH)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    rows, report = build_universe(
        args.audit, args.discovery_events, args.snapshot, args.protocol
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows.to_csv(args.output, index=False)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
