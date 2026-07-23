"""잠근 Rush 종목 고유 하방 비대칭 가설을 독립 티커 OOS에서 평가한다."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

from herd.independent_rush_evidence_v1 import extract_v61_rush_events
from herd.long_price_snapshot import verify_snapshot
from herd.rush_downside_asymmetry_universe_v1 import load_protocol
from herd.rush_episode_study_v2 import classify_path, load_protocol as load_path_protocol
from herd.rush_selector_comparison_v1 import load_protocol as load_selector_protocol


def _returns(frame: pd.DataFrame, name: str) -> pd.Series:
    result = frame.sort_values("Date").set_index("Date")["Adj Close"].astype(float)
    return np.log(result).diff().rename(name)


def aligned_factor_returns(
    stock: pd.DataFrame, sector: pd.DataFrame, spy: pd.DataFrame
) -> pd.DataFrame:
    joined = pd.concat(
        [_returns(stock, "stock"), _returns(sector, "sector"), _returns(spy, "spy")],
        axis=1,
        join="inner",
    ).dropna()
    joined["sector_excess"] = joined["sector"] - joined["spy"]
    return joined


def _semideviation(values: np.ndarray, downside: bool) -> float:
    selected = np.minimum(values, 0.0) if downside else np.maximum(values, 0.0)
    return float(np.sqrt(np.mean(np.square(selected))))


def asymmetry_score_at(
    factors: pd.DataFrame, observed_at: pd.Timestamp, protocol: dict
) -> float | None:
    spec = protocol["observation"]
    location = factors.index.searchsorted(pd.Timestamp(observed_at), side="right") - 1
    current = int(spec["current_window_sessions"])
    estimate = int(spec["estimation_window_sessions"])
    gap = int(spec["estimation_gap_sessions"])
    current_start = location - current + 1
    estimate_end = location - gap + 1
    if estimate_end != current_start:
        raise ValueError("estimation gap must equal the current observation window")
    estimate_start = estimate_end - estimate
    if estimate_start < 0 or location >= len(factors):
        return None
    training = factors.iloc[estimate_start:estimate_end]
    observation = factors.iloc[current_start:location + 1]
    if len(training) != estimate or len(observation) != current:
        return None
    x_train = np.column_stack([
        np.ones(len(training)),
        training["spy"].to_numpy(),
        training["sector_excess"].to_numpy(),
    ])
    coefficients, *_ = np.linalg.lstsq(x_train, training["stock"].to_numpy(), rcond=None)
    baseline_residual = training["stock"].to_numpy() - x_train @ coefficients
    x_current = np.column_stack([
        np.ones(len(observation)),
        observation["spy"].to_numpy(),
        observation["sector_excess"].to_numpy(),
    ])
    current_residual = observation["stock"].to_numpy() - x_current @ coefficients
    epsilon = float(spec["epsilon"])
    baseline_ratio = (
        _semideviation(baseline_residual, True) + epsilon
    ) / (_semideviation(baseline_residual, False) + epsilon)
    current_ratio = (
        _semideviation(current_residual, True) + epsilon
    ) / (_semideviation(current_residual, False) + epsilon)
    return float(math.log(current_ratio / baseline_ratio))


def attach_scores(
    events: pd.DataFrame,
    stock: pd.DataFrame,
    sector: pd.DataFrame,
    spy: pd.DataFrame,
    protocol: dict,
) -> pd.DataFrame:
    if events.empty:
        return events
    factors = aligned_factor_returns(stock, sector, spy)
    lag = int(protocol["observation"]["comparison_lag_sessions"])
    rows = []
    for event in events.to_dict("records"):
        observed = pd.Timestamp(event["last_observed_session"])
        position = factors.index.searchsorted(observed, side="right") - 1
        previous_at = factors.index[position - lag] if position >= lag else pd.NaT
        score = asymmetry_score_at(factors, observed, protocol)
        previous = (
            asymmetry_score_at(factors, previous_at, protocol)
            if pd.notna(previous_at) else None
        )
        rows.append(event | {
            "downside_asymmetry_score": score,
            "previous_score_5d": previous,
            "feature_cutoff_date": observed,
        })
    return pd.DataFrame(rows)


def _fold_id(date: pd.Timestamp, protocol: dict) -> str | None:
    for fold in protocol["time_folds"]:
        if pd.Timestamp(fold["start"]) <= date <= pd.Timestamp(fold["end"]):
            return str(fold["id"])
    return None


def _partial_sale_uplifts(
    frame: pd.DataFrame, event: dict, protocol: dict
) -> dict[str, float | str | None]:
    prices = frame.sort_values("Date").reset_index(drop=True).copy()
    dates = pd.to_datetime(prices["Date"])
    observed = pd.Timestamp(event["last_observed_session"])
    execution = dates.searchsorted(observed, side="right")
    result: dict[str, float | str | None] = {
        "execution_date": None,
        "execution_adjusted_open": None,
    }
    if execution >= len(prices):
        return result
    row = prices.iloc[execution]
    adjusted_open = float(row["Open"]) * float(row["Adj Close"]) / float(row["Close"])
    result["execution_date"] = pd.Timestamp(row["Date"]).date().isoformat()
    result["execution_adjusted_open"] = adjusted_open
    cost = 0.05 * float(protocol["target"]["one_way_cost_bps"]) / 10_000
    for horizon in protocol["target"]["economic_horizons_sessions"]:
        key = f"partial_sale_uplift_{horizon}d"
        target = execution + int(horizon) - 1
        result[key] = (
            0.05 * (1.0 - float(prices.iloc[target]["Adj Close"]) / adjusted_open) - cost
            if target < len(prices) else None
        )
    return result


def apply_sparse_transition_policy(panel: pd.DataFrame, protocol: dict) -> pd.DataFrame:
    if panel.empty:
        return panel
    threshold = float(protocol["observation"]["threshold"])
    candidates = panel[
        panel["downside_asymmetry_score"].gt(threshold)
        & panel["previous_score_5d"].le(threshold)
    ].sort_values(["ticker", "last_observed_session"]).copy()
    cooldown = int(protocol["observation"]["episode_cooldown_sessions"])
    annual_cap = int(protocol["observation"]["maximum_events_per_ticker_calendar_year"])
    accepted = []
    for _, group in candidates.groupby("ticker", sort=True):
        previous_position = -cooldown - 1
        year_counts: dict[int, int] = {}
        for index, row in group.iterrows():
            position = int(row["session_position"])
            year = pd.Timestamp(row["last_observed_session"]).year
            if position - previous_position < cooldown or year_counts.get(year, 0) >= annual_cap:
                continue
            accepted.append(index)
            previous_position = position
            year_counts[year] = year_counts.get(year, 0) + 1
    result = panel.copy()
    result["transition_triggered"] = False
    result.loc[accepted, "transition_triggered"] = True
    return result


def _rank_biserial_and_p(adverse: pd.Series, benign: pd.Series) -> tuple[float, float]:
    if adverse.empty or benign.empty:
        return float("nan"), 1.0
    test = mannwhitneyu(adverse, benign, alternative="greater")
    effect = 2.0 * float(test.statistic) / (len(adverse) * len(benign)) - 1.0
    return effect, float(test.pvalue)


def evaluate(panel: pd.DataFrame, protocol: dict) -> dict:
    gate = protocol["failure_gate"]
    adverse_labels = set(protocol["target"]["adverse_labels"])
    benign_labels = set(protocol["target"]["benign_labels"])
    resolved = panel[panel["path_label"].isin(adverse_labels | benign_labels)].copy()
    adverse = resolved[resolved["path_label"].isin(adverse_labels)]["downside_asymmetry_score"].dropna()
    benign = resolved[resolved["path_label"].isin(benign_labels)]["downside_asymmetry_score"].dropna()
    effect, p_value = _rank_biserial_and_p(adverse, benign)
    triggered = resolved[resolved["transition_triggered"]].copy()
    fold_rows = []
    for fold in protocol["time_folds"]:
        fold_frame = resolved[resolved["fold_id"].eq(fold["id"])]
        fold_adverse = fold_frame[fold_frame["path_label"].isin(adverse_labels)]["downside_asymmetry_score"].dropna()
        fold_benign = fold_frame[fold_frame["path_label"].isin(benign_labels)]["downside_asymmetry_score"].dropna()
        fold_effect, _ = _rank_biserial_and_p(fold_adverse, fold_benign)
        fold_rows.append({
            "fold_id": fold["id"],
            "events": int(len(fold_frame)),
            "directional_rank_biserial": None if np.isnan(fold_effect) else fold_effect,
        })
    annual = (
        triggered.assign(year=pd.to_datetime(triggered["last_observed_session"]).dt.year)
        .groupby(["ticker", "year"]).size()
    )
    median_annual = float(annual.median()) if len(annual) else 0.0
    missing = float(panel["downside_asymmetry_score"].isna().mean()) if len(panel) else 1.0
    median_uplift = (
        float(triggered["partial_sale_uplift_63d"].dropna().median())
        if triggered["partial_sale_uplift_63d"].notna().any() else None
    )
    checks = {
        "minimum_total_events": len(triggered) >= gate["minimum_total_events"],
        "minimum_adverse_events": int(triggered["path_label"].isin(adverse_labels).sum()) >= gate["minimum_adverse_events"],
        "minimum_benign_events": int(triggered["path_label"].isin(benign_labels).sum()) >= gate["minimum_benign_events"],
        "minimum_event_tickers": triggered["ticker"].nunique() >= gate["minimum_event_tickers"],
        "maximum_missing_fraction": missing <= gate["maximum_missing_fraction"],
        "maximum_median_annual_events": median_annual <= gate["maximum_median_annual_events_per_ticker"],
        "minimum_directional_effect": effect >= gate["minimum_directional_rank_biserial"],
        "maximum_one_sided_p_value": p_value <= gate["maximum_one_sided_p_value"],
        "minimum_positive_time_folds": sum(
            row["directional_rank_biserial"] is not None
            and row["directional_rank_biserial"] > 0 for row in fold_rows
        ) >= gate["minimum_positive_time_folds"],
        "required_time_folds": sum(row["events"] > 0 for row in fold_rows) >= gate["required_time_folds"],
        "minimum_median_63d_partial_sale_uplift": median_uplift is not None
        and median_uplift > gate["minimum_median_63d_partial_sale_uplift"],
    }
    admitted = all(checks.values())
    return {
        "report_version": "HERD_RUSH_DOWNSIDE_ASYMMETRY_OOS_V1",
        "status": "HYPOTHESIS_ADMITTED_FOR_CYCLE_RESEARCH" if admitted else "HYPOTHESIS_REJECTED",
        "rush_events": int(len(panel)),
        "resolved_events": int(len(resolved)),
        "triggered_events": int(len(triggered)),
        "triggered_tickers": int(triggered["ticker"].nunique()),
        "triggered_label_counts": triggered["path_label"].value_counts().to_dict(),
        "missing_fraction": missing,
        "directional_rank_biserial": None if np.isnan(effect) else effect,
        "one_sided_p_value": p_value,
        "median_annual_triggered_events": median_annual,
        "median_63d_partial_sale_uplift": median_uplift,
        "folds": fold_rows,
        "gate_checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "operational_action_authority": False,
        "herd_weight_change_allowed": False,
        "blind_holdout_access": False,
        "survivorship_safe": False,
    }


def run(
    snapshot_path: Path, universe_path: Path, protocol_path: Path
) -> tuple[pd.DataFrame, dict]:
    protocol = load_protocol(protocol_path)
    manifest = verify_snapshot(snapshot_path)
    universe = pd.read_csv(universe_path)
    selector_protocol = load_selector_protocol()
    path_protocol = load_path_protocol()
    tickers = universe["ticker"].tolist()
    sector_map = universe.set_index("ticker")["sector_etf"].to_dict()
    required = set(tickers) | set(sector_map.values()) | {"SPY"}
    frames = {
        ticker: pd.read_csv(
            snapshot_path / manifest["files"][ticker]["path"], parse_dates=["Date"]
        )
        for ticker in required
    }
    parts, failures = [], {}
    for ticker in tickers:
        try:
            stock = frames[ticker]
            events = extract_v61_rush_events(ticker, stock, selector_protocol)
            scored = attach_scores(
                events, stock, frames[sector_map[ticker]], frames["SPY"], protocol
            )
            if scored.empty:
                continue
            dates = pd.DatetimeIndex(pd.to_datetime(stock["Date"]))
            scored["session_position"] = scored["last_observed_session"].map(
                lambda value: dates.searchsorted(pd.Timestamp(value), side="right") - 1
            )
            close = stock.sort_values("Date").set_index("Date")["Adj Close"].astype(float)
            rows = []
            for event in scored.to_dict("records"):
                path = classify_path(close, pd.Series(event), path_protocol)
                if path is None:
                    continue
                date = pd.Timestamp(event["last_observed_session"])
                rows.append(
                    event
                    | path
                    | _partial_sale_uplifts(stock, event, protocol)
                    | {"sector_etf": sector_map[ticker], "fold_id": _fold_id(date, protocol)}
                )
            if rows:
                parts.append(pd.DataFrame(rows))
        except Exception as error:
            failures[ticker] = f"{type(error).__name__}: {error}"
    panel = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    if panel.empty:
        raise ValueError(f"no evaluable Rush events; failures={failures}")
    panel = apply_sparse_transition_policy(panel, protocol)
    report = evaluate(panel, protocol)
    report["snapshot_id"] = manifest["snapshot_id"]
    report["evaluated_universe_tickers"] = len(tickers)
    report["event_tickers"] = int(panel["ticker"].nunique())
    report["failures"] = failures
    if failures:
        report["status"] = "HYPOTHESIS_REJECTED"
        report["failed_checks"].append("zero_processing_failures")
    return panel, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=Path(__file__).with_name("rush_downside_asymmetry_protocol_v1.json"))
    parser.add_argument("--events-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()
    panel, report = run(args.snapshot, args.universe, args.protocol)
    args.events_output.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.events_output, index=False)
    args.report_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
