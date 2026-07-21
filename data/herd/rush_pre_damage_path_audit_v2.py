"""훼손 확인 전 거래일까지의 값이 이후 Rush 경로를 구분했는지 감사한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from herd.rush_damage_path_audit_v1 import (
    classify_path,
    compare_features,
    load_damage_events,
    observable_features,
    summarize,
)
from herd.rush_damage_profit_take_v1 import load_frames


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json")


def load_protocol(path: Path = PROTOCOL_PATH) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_PRE_DAMAGE_RESULTS":
        raise ValueError("strict pre-damage protocol must be locked")
    required = {"USE_DAMAGE_CONFIRMATION_SESSION_AS_FEATURE_INPUT", "AUTHORIZE_PROFIT_TAKE_FROM_THIS_AUDIT"}
    if not required.issubset(protocol.get("forbidden", [])):
        raise ValueError("strict pre-damage boundary weakened")
    return protocol


def previous_session(frame: pd.DataFrame, damage_date: pd.Timestamp) -> pd.Timestamp:
    dates = frame.loc[frame["Date"] < damage_date, "Date"].drop_duplicates().sort_values()
    if dates.empty:
        raise ValueError("no completed session before damage confirmation")
    return pd.Timestamp(dates.iloc[-1])


def build_panel(events: pd.DataFrame, frames: dict[str, pd.DataFrame], protocol: dict) -> pd.DataFrame:
    rows = []
    for _, event in events.iterrows():
        stock = frames[event["ticker"]]
        damage_date = pd.Timestamp(event["damage_date"])
        path = classify_path(stock, damage_date, protocol)
        if path is None:
            continue
        cutoff = previous_session(stock, damage_date)
        features = observable_features(stock, frames["SPY"], frames[event["sector_etf"]], cutoff)
        rows.append({**event.to_dict(), "feature_cutoff_date": cutoff, **path, **features})
    return pd.DataFrame(rows)


def run(protocol_path: Path = PROTOCOL_PATH) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    protocol = load_protocol(protocol_path)
    events = load_damage_events(ROOT / protocol["source_events"], protocol)
    frames = load_frames(ROOT / protocol["snapshot"], set(events["ticker"]) | {"SPY"} | set(events["sector_etf"]))
    panel = build_panel(events, frames, protocol)
    if not (pd.to_datetime(panel["feature_cutoff_date"]) < pd.to_datetime(panel["damage_date"])).all():
        raise ValueError("damage confirmation leaked into feature input")
    comparison = compare_features(panel, protocol)
    report = summarize(panel, comparison, protocol)
    report["report_version"] = "HERD_RUSH_PRE_DAMAGE_PATH_AUDIT_V2"
    report["feature_cutoff"] = protocol["feature_cutoff"]
    report["decision"] = "DISCOVERY_LEADS_REQUIRE_NEW_SAMPLE" if report["retained_count"] else "CURRENT_PRE_DAMAGE_PRICE_VOLUME_PROFIT_TAKE_MODEL_NOT_IDENTIFIED"
    report["model_fit"]["reason"] = "Before the confirmation session, no candidate met material effect, Holm significance, and same-direction evidence in all three eras. The confirmation-day move created the apparent V1 separation too late to be predictive."
    report["strongest_pre_damage_observations"] = comparison.sort_values(
        "directional_rank_biserial", ascending=False
    )[["feature", "directional_rank_biserial", "holm_p_value", "directional_eras", "passes_univariate_gate"]].head(3).to_dict("records")
    report["interpretation"] = "No repeated pre-confirmation separator was identified. With the currently audited price and volume observations, the sparse profit-take model is not realizable; new information families or a new independently preregistered hypothesis are required."
    return panel, comparison, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    panel, comparison, report = run()
    panel.to_csv(args.events, index=False)
    comparison.to_json(args.comparison, orient="records", indent=2)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
