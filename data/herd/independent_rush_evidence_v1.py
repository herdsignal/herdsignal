"""잠근 V61 Rush 선택자에서 네 가격 증거를 388개 독립 종목군으로 검증한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from herd.herd_candidate_features_v2 import _daily_features, _trend_quality
from herd.indicator_inventory import build_v4_indicator_frame
from herd.legacy_model_evaluation import v4_base_score, v61_actions
from herd.long_price_snapshot import verify_snapshot
from herd.rush_episode_study_v2 import classify_path, load_protocol as load_path_protocol
from herd.rush_path_comparison_v2 import _holm, _rank_biserial
from herd.rush_selector_comparison_v1 import collapse_v61_rush_events, load_protocol as load_selector_protocol
from herd.weekly_rsi_events import completed_weekly_bars


DEFAULT_PROTOCOL = Path(__file__).with_name("independent_evidence_protocol_v1.json")
FEATURE_DIRECTIONS = {
    "SECTOR_RS_DAMAGE_DELTA_4W": 1.0,
    "TREND_QUALITY_DELTA_4W": -1.0,
    "PARTICIPATION_WEAKENING_DELTA_4W": 1.0,
    "MARKET_STRESS_DELTA_4W": 1.0,
}


def load_protocol(path: Path = DEFAULT_PROTOCOL) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_INDEPENDENT_RESULTS":
        raise ValueError("independent evidence protocol must be locked")
    if "COMBINE_FAILED_HYPOTHESES" not in protocol.get("forbidden", []):
        raise ValueError("failed hypothesis combination must be forbidden")
    features = {row["feature"] for row in protocol["hypotheses"]}
    if features != set(FEATURE_DIRECTIONS):
        raise ValueError("hypothesis set changed")
    return protocol


def extract_v61_rush_events(ticker: str, frame: pd.DataFrame, selector_protocol: dict) -> pd.DataFrame:
    raw = frame.copy().sort_values("Date")
    raw["Date"] = pd.to_datetime(raw["Date"])
    close = raw.set_index("Date")["Adj Close"].astype(float)
    score = v4_base_score(build_v4_indicator_frame(raw))
    if score.empty:
        return pd.DataFrame()
    aligned_close = close.loc[score.index.min():]
    decisions = v61_actions(aligned_close, score.reindex(aligned_close.index).ffill()).reset_index()
    decisions = decisions.rename(columns={decisions.columns[0]: "signal_date"})
    decisions["ticker"] = ticker
    rush = collapse_v61_rush_events(decisions, selector_protocol)
    if rush.empty:
        return pd.DataFrame(columns=[
            "ticker", "episode_id", "signal_date", "last_observed_session", "source_regime"
        ])
    start = pd.Timestamp(selector_protocol["analysis_window"]["start_inclusive"])
    end = pd.Timestamp(selector_protocol["analysis_window"]["signal_end_inclusive"])
    return rush[rush["last_observed_session"].between(start, end)].copy()


def weekly_transition_features(stock: pd.DataFrame, sector: pd.DataFrame, spy: pd.DataFrame) -> pd.DataFrame:
    daily = _daily_features(stock, sector, spy)
    weekly = completed_weekly_bars(stock).copy()
    sessions = pd.DatetimeIndex(pd.to_datetime(weekly["last_session"]))
    observed = daily.reindex(sessions, method="ffill")
    quality = [np.nan] * len(weekly)
    for index in range(25, len(weekly)):
        quality[index] = _trend_quality(weekly["Adj Close"].iloc[index - 25:index + 1])
    result = pd.DataFrame({
        "last_observed_session": sessions,
        "SECTOR_RS_DAMAGE": observed["STOCK_SECTOR_RS_DAMAGE"].to_numpy(),
        "TREND_QUALITY": quality,
        "PARTICIPATION_WEAKENING": observed["SIGNED_VOLUME_PARTICIPATION"].to_numpy(),
        "MARKET_STRESS": observed["MARKET_STRESS_REGIME"].to_numpy(),
    })
    for source, target in (
        ("SECTOR_RS_DAMAGE", "SECTOR_RS_DAMAGE_DELTA_4W"),
        ("TREND_QUALITY", "TREND_QUALITY_DELTA_4W"),
        ("PARTICIPATION_WEAKENING", "PARTICIPATION_WEAKENING_DELTA_4W"),
        ("MARKET_STRESS", "MARKET_STRESS_DELTA_4W"),
    ):
        result[target] = result[source].diff(4)
    return result[["last_observed_session", *FEATURE_DIRECTIONS]]


def attach_features_and_paths(events: pd.DataFrame, stock: pd.DataFrame, sector: pd.DataFrame, spy: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return events
    features = weekly_transition_features(stock, sector, spy).sort_values("last_observed_session")
    left = events.sort_values("last_observed_session")
    panel = pd.merge_asof(left, features, on="last_observed_session", direction="backward")
    close = stock.sort_values("Date").set_index("Date")["Adj Close"].astype(float)
    path_protocol = load_path_protocol()
    rows = []
    for event in panel.to_dict("records"):
        path = classify_path(close, pd.Series(event), path_protocol)
        if path is not None:
            rows.append(event | path)
    return pd.DataFrame(rows)


def _era_effects(eligible: pd.DataFrame, feature: str, direction: float, protocol: dict) -> list[dict]:
    result = []
    treatment_labels = protocol["target"]["treatment_labels"]
    control_labels = protocol["target"]["control_labels"]
    for start, end in protocol["gate"]["eras"]:
        era = eligible[eligible["last_observed_session"].between(pd.Timestamp(start), pd.Timestamp(end))]
        treatment = era[era["path_label"].isin(treatment_labels)][feature].dropna()
        control = era[era["path_label"].isin(control_labels)][feature].dropna()
        effect = None
        if len(treatment) >= 20 and len(control) >= 20:
            effect = _rank_biserial(treatment, control)[0] * direction
        result.append({"start": start, "end": end, "directional_rank_biserial": effect})
    return result


def evaluate(panel: pd.DataFrame, protocol: dict) -> pd.DataFrame:
    labels = protocol["target"]["treatment_labels"] + protocol["target"]["control_labels"]
    eligible = panel[panel["path_label"].isin(labels)].copy()
    rows = []
    for hypothesis in protocol["hypotheses"]:
        feature = hypothesis["feature"]
        direction = FEATURE_DIRECTIONS[feature]
        treatment = eligible[eligible["path_label"].isin(protocol["target"]["treatment_labels"])][feature].dropna()
        control = eligible[eligible["path_label"].isin(protocol["target"]["control_labels"])][feature].dropna()
        effect, p_value = _rank_biserial(treatment, control) if len(treatment) and len(control) else (np.nan, 1.0)
        era_effects = _era_effects(eligible, feature, direction, protocol)
        rows.append({
            "hypothesis": hypothesis["id"],
            "priority": hypothesis["priority"],
            "feature": feature,
            "treatment_events": int(len(treatment)),
            "control_events": int(len(control)),
            "missing_fraction": float(eligible[feature].isna().mean()),
            "treatment_median": float(treatment.median()) if len(treatment) else None,
            "control_median": float(control.median()) if len(control) else None,
            "raw_rank_biserial": float(effect),
            "directional_rank_biserial": float(effect * direction),
            "raw_p_value": float(p_value),
            "era_effects": era_effects,
            "positive_eras": sum(item["directional_rank_biserial"] is not None and item["directional_rank_biserial"] > 0 for item in era_effects),
        })
    _holm(rows)
    gate = protocol["gate"]
    for row in rows:
        row["admitted"] = bool(
            row["treatment_events"] >= gate["minimum_treatment_events"]
            and row["control_events"] >= gate["minimum_control_events"]
            and row["missing_fraction"] <= gate["maximum_missing_fraction"]
            and row["directional_rank_biserial"] >= gate["minimum_directional_rank_biserial"]
            and row["holm_p_value"] <= gate["maximum_holm_p_value"]
            and row["positive_eras"] >= gate["required_positive_eras"]
        )
    return pd.DataFrame(rows).sort_values("priority")


def run(snapshot: Path, universe_audit: Path, protocol_path: Path = DEFAULT_PROTOCOL) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    protocol = load_protocol(protocol_path)
    selector_protocol = load_selector_protocol()
    manifest = verify_snapshot(snapshot)
    audit = pd.read_csv(universe_audit)
    tickers = audit.loc[audit["eligible"].astype(bool), "ticker"].tolist()
    required = sorted(set(tickers) | {"SPY"} | set(audit.loc[audit["eligible"].astype(bool), "sector_etf"]))
    frames = {
        ticker: pd.read_csv(snapshot / manifest["files"][ticker]["path"], parse_dates=["Date"])
        for ticker in required
    }
    sector_map = audit.set_index("ticker")["sector_etf"].to_dict()
    parts, failures = [], {}
    for ticker in tickers:
        try:
            events = extract_v61_rush_events(ticker, frames[ticker], selector_protocol)
            panel = attach_features_and_paths(events, frames[ticker], frames[sector_map[ticker]], frames["SPY"])
            if not panel.empty:
                panel["sector_etf"] = sector_map[ticker]
                parts.append(panel)
        except Exception as exc:
            failures[ticker] = f"{type(exc).__name__}: {exc}"
    panel = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    table = evaluate(panel, protocol)
    admitted = table.loc[table["admitted"], "feature"].tolist()
    report = {
        "report_version": "HERD_INDEPENDENT_RUSH_EVIDENCE_V1",
        "status": "INDEPENDENT_OOS_COMPLETE" if not failures else "INDEPENDENT_OOS_WITH_FAILURES",
        "claim_boundary": "CURRENT_CONSTITUENTS_ROBUSTNESS_ONLY",
        "snapshot_id": manifest["snapshot_id"],
        "snapshot_sha256": manifest["snapshot_sha256"],
        "eligible_tickers": len(tickers),
        "evaluated_tickers": int(panel["ticker"].nunique()) if not panel.empty else 0,
        "episodes": len(panel),
        "admitted_features": admitted,
        "admitted_count": len(admitted),
        "sec_pit_business_state": protocol["sec_pit_business_state"],
        "operational_action_authority": False,
        "blind_holdout_access": False,
        "failures": failures,
    }
    return panel, table, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--universe-audit", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--panel-output", type=Path, required=True)
    parser.add_argument("--comparison-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()
    panel, table, report = run(args.snapshot, args.universe_audit, args.protocol)
    args.panel_output.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.panel_output, index=False)
    table.to_json(args.comparison_output, orient="records", indent=2)
    args.report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
