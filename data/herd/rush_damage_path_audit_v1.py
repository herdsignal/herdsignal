"""Rush 훼손 뒤 경로와 훼손일까지 관측 가능한 분리 변수를 감사한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from herd.rush_damage_profit_take_v1 import load_frames
from herd.rush_path_comparison_v2 import _holm, _rank_biserial


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json")


def load_protocol(path: Path = PROTOCOL_PATH) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_PATH_AND_FEATURE_RESULTS":
        raise ValueError("Rush damage path audit protocol must be locked")
    required = {"USE_POST_DAMAGE_VALUES_AS_FEATURES", "AUTHORIZE_PROFIT_TAKE_FROM_THIS_AUDIT"}
    if not required.issubset(protocol.get("forbidden", [])):
        raise ValueError("path audit leakage or action boundary weakened")
    return protocol


def load_damage_events(path: Path, protocol: dict) -> pd.DataFrame:
    source = pd.read_csv(path)
    required = {"ticker", "episode_id", "signal_date", "sector_etf", "damage_date", "damage_triggered"}
    if not required.issubset(source):
        raise ValueError("Rush damage event schema mismatch")
    events = source[source["damage_triggered"].eq(True)].copy()
    if len(events) != protocol["eligibility"]["expected_source_event_count"]:
        raise ValueError(f"expected 1,998 damage events, found {len(events)}")
    events["signal_date"] = pd.to_datetime(events["signal_date"])
    events["damage_date"] = pd.to_datetime(events["damage_date"])
    return events


def _close(frame: pd.DataFrame) -> pd.Series:
    return frame.drop_duplicates("Date").set_index("Date")["Adj Close"].astype(float).sort_index()


def _returns(series: pd.Series, sessions: int) -> float:
    return float(series.iloc[-1] / series.iloc[-sessions - 1] - 1)


def classify_path(stock: pd.DataFrame, damage_date: pd.Timestamp, protocol: dict) -> dict | None:
    close = _close(stock)
    position = close.index.searchsorted(damage_date, side="right") - 1
    horizon = protocol["future_path"]["horizon_sessions"]
    if position < 0 or close.index[position] != damage_date or position + horizon >= len(close):
        return None
    anchor = float(close.iloc[position])
    future = close.iloc[position + 1:position + horizon + 1] / anchor - 1
    adverse, favorable, terminal = float(future.min()), float(future.max()), float(future.iloc[-1])
    rules = protocol["future_path"]
    structural = rules["structural_break"]
    if terminal <= structural["terminal_return_maximum"] or adverse <= structural["minimum_adverse_return_maximum"]:
        label = "STRUCTURAL_BREAK"
    elif adverse <= rules["large_pullback"]["minimum_adverse_return_maximum"]:
        label = "LARGE_PULLBACK"
    elif terminal >= rules["resumed_uptrend"]["terminal_return_minimum"] and favorable >= rules["resumed_uptrend"]["maximum_favorable_return_minimum"]:
        label = "RESUMED_UPTREND"
    else:
        label = "TEMPORARY_PULLBACK"
    return {
        "path_label": label,
        "path_minimum_return_63d": adverse,
        "path_maximum_return_63d": favorable,
        "path_terminal_return_63d": terminal,
        "path_end": close.index[position + horizon],
    }


def observable_features(stock: pd.DataFrame, spy: pd.DataFrame, sector: pd.DataFrame, damage_date: pd.Timestamp) -> dict:
    stock_frame = stock.drop_duplicates("Date").set_index("Date").sort_index()
    aligned = pd.concat({
        "stock": stock_frame["Adj Close"].astype(float),
        "spy": _close(spy),
        "sector": _close(sector),
    }, axis=1, join="inner").dropna().loc[:damage_date]
    if len(aligned) < 85 or aligned.index[-1] != damage_date:
        return {name: np.nan for name in (
            "breakdown_severity_vol20", "below_sma50_severity_vol63", "relative_damage_21d",
            "downside_acceleration_5_21", "down_up_volume_ratio_20d", "realized_vol_expansion_20_63",
        )}
    close = aligned["stock"]
    returns = close.pct_change()
    vol20 = max(float(returns.iloc[-20:].std()), 1e-8)
    vol63 = max(float(returns.iloc[-63:].std()), 1e-8)
    prior_low = float(close.iloc[-21:-1].min())
    sma50 = float(close.iloc[-50:].mean())
    current = float(close.iloc[-1])
    r5, r21 = _returns(close, 5), _returns(close, 21)
    benchmark21 = (_returns(aligned["spy"], 21) + _returns(aligned["sector"], 21)) / 2

    recent_dates = aligned.index[-21:]
    volume_returns = stock_frame.reindex(recent_dates)[["Adj Close", "Volume"]].copy()
    volume_returns["return"] = volume_returns["Adj Close"].astype(float).pct_change()
    down = volume_returns.loc[volume_returns["return"] < 0, "Volume"].astype(float)
    up = volume_returns.loc[volume_returns["return"] > 0, "Volume"].astype(float)
    volume_ratio = float(down.mean() / up.mean()) if len(down) and len(up) and up.mean() > 0 else np.nan
    prior_vol63 = float(returns.iloc[-83:-20].std())
    return {
        "breakdown_severity_vol20": max(prior_low / current - 1, 0.0) / vol20,
        "below_sma50_severity_vol63": max(sma50 / current - 1, 0.0) / vol63,
        "relative_damage_21d": benchmark21 - r21,
        "downside_acceleration_5_21": r21 * 5 / 21 - r5,
        "down_up_volume_ratio_20d": volume_ratio,
        "realized_vol_expansion_20_63": vol20 / prior_vol63 if np.isfinite(prior_vol63) and prior_vol63 > 0 else np.nan,
    }


def build_panel(events: pd.DataFrame, frames: dict[str, pd.DataFrame], protocol: dict) -> pd.DataFrame:
    rows = []
    for _, event in events.iterrows():
        damage_date = pd.Timestamp(event["damage_date"])
        path = classify_path(frames[event["ticker"]], damage_date, protocol)
        if path is None:
            continue
        features = observable_features(frames[event["ticker"]], frames["SPY"], frames[event["sector_etf"]], damage_date)
        rows.append({**event.to_dict(), **path, **features})
    return pd.DataFrame(rows)


def compare_features(panel: pd.DataFrame, protocol: dict) -> pd.DataFrame:
    comparison, gate = protocol["comparison"], protocol["retention_gate"]
    adverse = panel["path_label"].isin(comparison["treatment_labels"])
    rows = []
    for candidate in protocol["candidate_features"]:
        feature = candidate["id"]
        treatment, control = panel.loc[adverse, feature].dropna(), panel.loc[~adverse, feature].dropna()
        effect, p_value = _rank_biserial(treatment, control) if len(treatment) and len(control) else (np.nan, 1.0)
        era_effects = []
        for start, end in gate["eras"]:
            era = panel[panel["damage_date"].between(pd.Timestamp(start), pd.Timestamp(end))]
            era_adverse = era["path_label"].isin(comparison["treatment_labels"])
            left, right = era.loc[era_adverse, feature].dropna(), era.loc[~era_adverse, feature].dropna()
            enough = min(len(left), len(right)) >= gate["minimum_events_per_side_per_era"]
            era_effect = _rank_biserial(left, right)[0] if enough else None
            era_effects.append({"start": start, "end": end, "treatment_events": len(left), "control_events": len(right), "directional_rank_biserial": era_effect})
        rows.append({
            "feature": feature,
            "expected_direction": candidate["expected_direction"],
            "treatment_events": len(treatment), "control_events": len(control),
            "missing_fraction": float(panel[feature].isna().mean()),
            "treatment_median": float(treatment.median()) if len(treatment) else None,
            "control_median": float(control.median()) if len(control) else None,
            "directional_rank_biserial": float(effect), "raw_p_value": float(p_value),
            "era_effects": era_effects,
            "directional_eras": sum(item["directional_rank_biserial"] is not None and item["directional_rank_biserial"] > 0 for item in era_effects),
        })
    _holm(rows)
    for row in rows:
        row["passes_univariate_gate"] = bool(
            min(row["treatment_events"], row["control_events"]) >= gate["minimum_events_per_side"]
            and row["missing_fraction"] <= gate["maximum_missing_fraction"]
            and row["directional_rank_biserial"] >= gate["minimum_directional_rank_biserial"]
            and row["holm_p_value"] <= gate["maximum_holm_p_value"]
            and row["directional_eras"] >= gate["minimum_directional_eras"]
        )
        row["retained_for_new_sample_preregistration"] = False
        row["redundancy_reason"] = None
    candidates = sorted((row for row in rows if row["passes_univariate_gate"]), key=lambda row: row["directional_rank_biserial"], reverse=True)
    retained = []
    for row in candidates:
        conflicts = []
        for selected in retained:
            pair = panel[[row["feature"], selected["feature"]]].dropna()
            correlation = float(spearmanr(pair.iloc[:, 0], pair.iloc[:, 1]).statistic) if len(pair) >= 30 else np.nan
            if np.isfinite(correlation) and abs(correlation) > gate["maximum_pairwise_spearman_correlation"]:
                conflicts.append(f"CORRELATED_WITH_{selected['feature']}:{correlation:.3f}")
        if conflicts:
            row["redundancy_reason"] = ";".join(conflicts)
        else:
            row["retained_for_new_sample_preregistration"] = True
            retained.append(row)
    return pd.DataFrame(rows)


def summarize(panel: pd.DataFrame, comparison: pd.DataFrame, protocol: dict) -> dict:
    counts = panel["path_label"].value_counts().to_dict()
    retained = comparison.loc[comparison["retained_for_new_sample_preregistration"], "feature"].tolist()
    source_report = json.loads((ROOT / protocol["source_report"]).read_text(encoding="utf-8"))
    source_protocol = json.loads((ROOT / protocol["source_protocol"]).read_text(encoding="utf-8"))
    benign = counts.get("TEMPORARY_PULLBACK", 0) + counts.get("RESUMED_UPTREND", 0)
    profiles = {}
    profile_columns = [candidate["id"] for candidate in protocol["candidate_features"]]
    for label, group in panel.groupby("path_label"):
        profiles[label] = {
            "events": len(group),
            "median_damage_wait_sessions": float(group["damage_wait_sessions"].median()),
            "median_features": {feature: float(group[feature].median()) for feature in profile_columns},
        }
    failures = []
    source_rate = len(panel) / protocol["eligibility"]["expected_source_event_count"]
    if source_rate < 1:
        failures.append("INCOMPLETE_FIXED_HORIZON_PATHS")
    if not retained:
        failures.append("NO_REPEATED_PRE_DAMAGE_SEPARATOR")
    if comparison["directional_rank_biserial"].max() < protocol["retention_gate"]["minimum_directional_rank_biserial"]:
        failures.append("FEATURE_EFFECTS_TOO_SMALL")
    if comparison["directional_eras"].max() < protocol["retention_gate"]["minimum_directional_eras"]:
        failures.append("FEATURE_DIRECTION_NOT_STABLE_ACROSS_ERAS")
    if source_report["damage_rate"] > source_protocol["adoption_gate"]["maximum_damage_rate"]:
        failures.append("DAMAGE_TRIGGER_NOT_SPARSE")
    if benign / len(panel) > 0.50:
        failures.append("MOST_CONFIRMED_DAMAGE_PATHS_ARE_BENIGN")
    if retained:
        failures.append("DISCOVERY_LEADS_HAVE_NO_INDEPENDENT_CONFIRMATION")
    return {
        "report_version": "HERD_RUSH_DAMAGE_PATH_AUDIT_V1",
        "status": "DIAGNOSTIC_COMPLETE",
        "decision": "DISCOVERY_LEADS_REQUIRE_NEW_SAMPLE" if retained else "CURRENT_PRICE_VOLUME_PROFIT_TAKE_MODEL_NOT_IDENTIFIED",
        "source_damage_events": protocol["eligibility"]["expected_source_event_count"],
        "classified_events": len(panel), "tickers": int(panel["ticker"].nunique()),
        "path_counts": counts, "path_fractions": {key: value / len(panel) for key, value in counts.items()},
        "path_profiles": profiles,
        "features_audited": len(comparison), "retained_features": retained, "retained_count": len(retained),
        "failure_causes": failures,
        "model_fit": {
            "source_damage_rate": source_report["damage_rate"],
            "source_maximum_damage_rate": source_protocol["adoption_gate"]["maximum_damage_rate"],
            "benign_path_fraction_after_damage": benign / len(panel),
            "existing_profit_take_rule_passed": False,
            "reason": "The existing trigger is too common and mostly precedes benign paths. Two same-sample leads are not sufficient to repair or authorize it."
        },
        "interpretation": "The existing profit-take model remains rejected. Downside acceleration and volatility expansion are discovery leads for a separately locked independent sample, not evidence for threshold tuning on these events.",
        "profit_take_authorized": False, "operational_action_ratio": 0.0,
        "same_sample_confirmation_allowed": False, "blind_holdout_access": False,
        "survivorship_safe": False, "claim_boundary": "CURRENT_CONSTITUENTS_DIAGNOSTIC_ONLY",
    }


def run(protocol_path: Path = PROTOCOL_PATH) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    protocol = load_protocol(protocol_path)
    events = load_damage_events(ROOT / protocol["source_events"], protocol)
    tickers = set(events["ticker"]) | {"SPY"} | set(events["sector_etf"])
    frames = load_frames(ROOT / protocol["snapshot"], tickers)
    panel = build_panel(events, frames, protocol)
    comparison = compare_features(panel, protocol)
    return panel, comparison, summarize(panel, comparison, protocol)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    panel, comparison, report = run()
    args.events.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.events, index=False)
    comparison.to_json(args.comparison, orient="records", indent=2)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
