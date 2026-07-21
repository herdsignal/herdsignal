"""동일 섹터 동료 종목의 고점 이탈과 상승 참여 폭 변화를 독립 비교한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from herd.reentry_feature_discovery_v1 import compare


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json")
FEATURES = ["PEER_HIGH_EXIT_SHARE_DELTA_4W", "PEER_ADVANCE_BREADTH_DELTA_4W"]


def load_protocol(path: Path = PROTOCOL_PATH) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_FEATURE_RESULTS" or protocol.get("claim_boundary") != "CURRENT_CONSTITUENTS_ROBUSTNESS_ONLY":
        raise ValueError("peer breadth protocol boundary is not locked")
    if [row["id"] for row in protocol["candidate_features"]] != FEATURES:
        raise ValueError("peer breadth candidate set changed")
    return protocol


def leave_one_out_share(indicator: pd.DataFrame, minimum_peers: int) -> dict[str, pd.Series]:
    valid = indicator.notna()
    totals = indicator.fillna(0).sum(axis=1)
    counts = valid.sum(axis=1)
    result = {}
    for ticker in indicator.columns:
        peer_count = counts - valid[ticker].astype(int)
        peer_total = totals - indicator[ticker].fillna(0)
        result[ticker] = (peer_total / peer_count.replace(0, np.nan)).where(peer_count >= minimum_peers)
    return result


def sector_feature_series(close: pd.DataFrame, protocol: dict) -> dict[str, pd.DataFrame]:
    measurement = protocol["measurement"]
    near_high = close.div(close.rolling(measurement["high_window_weeks"], min_periods=measurement["high_window_weeks"]).max()).ge(measurement["near_high_ratio"])
    near_high = near_high.where(close.notna())
    advancing = close.pct_change(measurement["advance_return_weeks"], fill_method=None).gt(0).where(close.notna())
    minimum = protocol["peer_definition"]["minimum_peers"]
    high_shares = leave_one_out_share(near_high.astype(float).where(near_high.notna()), minimum)
    advance_shares = leave_one_out_share(advancing.astype(float).where(advancing.notna()), minimum)
    lag = measurement["change_lag_weeks"]
    return {
        ticker: pd.DataFrame({
            FEATURES[0]: (1 - high_shares[ticker]).diff(lag),
            FEATURES[1]: advance_shares[ticker].diff(lag),
        }) for ticker in close.columns
    }


def build_feature_map(snapshot: Path, audit_path: Path, protocol: dict) -> dict[str, pd.DataFrame]:
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    audit = pd.read_csv(audit_path)
    audit = audit[audit["eligible"].astype(bool)]
    output = {}
    for _, sector in audit.groupby("gics_sector"):
        series = {}
        for ticker in sector["ticker"]:
            frame = pd.read_csv(snapshot / manifest["files"][ticker]["path"], parse_dates=["Date"])
            series[ticker] = frame.set_index("Date")["Adj Close"].resample("W-FRI").last()
        close = pd.DataFrame(series).sort_index()
        output.update(sector_feature_series(close, protocol))
    return output


def attach_features(targets: pd.DataFrame, feature_map: dict[str, pd.DataFrame]) -> pd.DataFrame:
    groups = []
    for ticker, events in targets.groupby("ticker", sort=True):
        left = events.copy()
        left["signal_date"] = pd.to_datetime(left["signal_date"])
        right = feature_map[ticker].reset_index().rename(columns={"Date": "feature_week", "index": "feature_week"})
        merged = pd.merge_asof(left.sort_values("signal_date"), right.sort_values("feature_week"), left_on="signal_date", right_on="feature_week", direction="backward")
        if (merged["feature_week"] > merged["signal_date"]).any():
            raise ValueError("post-signal peer breadth leaked")
        groups.append(merged)
    return pd.concat(groups, ignore_index=True)


def evaluate(panel: pd.DataFrame, protocol: dict) -> pd.DataFrame:
    adapter = {"candidate_features": protocol["candidate_features"], "comparison": protocol["comparison"], "retention_gate": {**protocol["retention_gate"], "minimum_absolute_rank_biserial": protocol["retention_gate"]["minimum_directional_rank_biserial"]}}
    table = compare(panel, adapter)
    directions = {row["id"]: row["expected_direction"] for row in protocol["candidate_features"]}
    table["expected_direction"] = table["feature"].map(directions)
    threshold = protocol["retention_gate"]["minimum_directional_rank_biserial"]
    table["direction_matched"] = table.apply(lambda row: row["rank_biserial"] >= threshold if row["expected_direction"] == "HIGHER" else row["rank_biserial"] <= -threshold, axis=1)
    table["retained_for_new_sample_preregistration"] &= table["direction_matched"]
    return table


def run(protocol_path: Path = PROTOCOL_PATH) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    protocol = load_protocol(protocol_path)
    if json.loads((ROOT / protocol["target_report"]).read_text(encoding="utf-8")).get("status") != "DISCOVERY_TARGET_READY":
        raise ValueError("reentry target is not ready")
    targets = pd.read_csv(ROOT / protocol["target_rows"])
    feature_map = build_feature_map(ROOT / protocol["snapshot"], ROOT / protocol["universe_audit"], protocol)
    panel = attach_features(targets, feature_map)
    comparison = evaluate(panel, protocol)
    retained = comparison.loc[comparison["retained_for_new_sample_preregistration"], "feature"].tolist()
    report = {"report_version": "HERD_PEER_CLUSTER_BREADTH_V1", "status": "DISCOVERY_COMPLETE", "claim_boundary": protocol["claim_boundary"], "target_events": len(panel), "features_compared": len(FEATURES), "retained_features": retained, "independent_oos_passed_features": [], "survivorship_safe": False, "operational_action_ratio": 0.0, "blind_holdout_access": False}
    return panel, comparison, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True); parser.add_argument("--comparison", type=Path, required=True); parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(); panel, comparison, report = run()
    panel.to_csv(args.panel, index=False); comparison.to_json(args.comparison, orient="records", indent=2)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
