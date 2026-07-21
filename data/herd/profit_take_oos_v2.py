"""V2 가격 측정법의 episode 사건을 만들고 독립 OOS gate를 평가한다."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

from herd.profit_take_measurements_v2 import (
    MEASUREMENT_COLUMNS,
    calculate_measurements,
    load_registry,
)
from herd.validation_universe import TICKER_SECTOR_ETF


def extract_episode_events(
    percentile: pd.Series,
    *,
    threshold: float,
    reset: float,
) -> pd.DatetimeIndex:
    """고점 episode마다 최초 진입 한 번만 반환한다."""
    active = False
    dates: list[pd.Timestamp] = []
    for when, value in percentile.dropna().items():
        if active and value <= reset:
            active = False
        if not active and value >= threshold:
            dates.append(pd.Timestamp(when))
            active = True
    return pd.DatetimeIndex(dates)


def _sample_controls(
    percentile: pd.Series,
    *,
    lower: float,
    upper: float,
    spacing_days: int,
) -> pd.DatetimeIndex:
    candidates = percentile[(percentile >= lower) & (percentile <= upper)].dropna()
    dates: list[pd.Timestamp] = []
    last: pd.Timestamp | None = None
    for when in candidates.index:
        current = pd.Timestamp(when)
        if last is None or (current - last).days >= spacing_days:
            dates.append(current)
            last = current
    return pd.DatetimeIndex(dates)


def _outcome(
    date: pd.Timestamp,
    stock: pd.Series,
    sector: pd.Series,
    horizon: int,
) -> dict | None:
    stock = stock.dropna().sort_index()
    sector = sector.dropna().sort_index()
    position = stock.index.searchsorted(date, side="right") - 1
    if position < 0 or position + horizon >= len(stock):
        return None
    start_date = stock.index[position]
    end_date = stock.index[position + horizon]
    path = stock.iloc[position + 1:position + horizon + 1]
    sector_start = sector.loc[:start_date]
    sector_end = sector.loc[:end_date]
    if path.empty or sector_start.empty or sector_end.empty:
        return None
    start = float(stock.iloc[position])
    stock_return = float(stock.iloc[position + horizon] / start - 1)
    sector_return = float(sector_end.iloc[-1] / sector_start.iloc[-1] - 1)
    return {
        "outcome_end": end_date,
        "forward_return": stock_return,
        "forward_excess_return": stock_return - sector_return,
        "forward_trough_return": float(path.min() / start - 1),
        "forward_upside_return": float(path.max() / start - 1),
    }


def build_events_for_ticker(
    ticker: str,
    stock: pd.DataFrame,
    sector: pd.DataFrame,
    spy: pd.DataFrame,
    registry: dict,
) -> pd.DataFrame:
    stock_close = stock.set_index("Date")["Adj Close"]
    sector_close = sector.set_index("Date")["Adj Close"]
    spy_close = spy.set_index("Date")["Adj Close"]
    measurements = calculate_measurements(stock_close, sector_close, spy_close)
    monthly = measurements.resample("ME").last()
    reset = registry["observation"]["episode_reset_percentile"]
    control_band = registry["observation"]["control_percentile_band"]
    rows: list[dict] = []
    for hypothesis in registry["hypotheses"]:
        hypothesis_id = hypothesis["id"]
        percentile = monthly[f"{hypothesis_id}_percentile"]
        for threshold in hypothesis["event_percentiles"]:
            treatment_dates = extract_episode_events(
                percentile, threshold=threshold, reset=reset
            )
            controls = _sample_controls(
                percentile,
                lower=control_band[0],
                upper=control_band[1],
                spacing_days=max(registry["observation"]["forward_horizons_days"]),
            )
            for group, dates in (("TREATMENT", treatment_dates), ("CONTROL", controls)):
                for signal_date in dates:
                    for horizon in registry["observation"]["forward_horizons_days"]:
                        outcome = _outcome(signal_date, stock_close, sector_close, horizon)
                        if outcome is not None:
                            rows.append({
                                "ticker": ticker,
                                "hypothesis_id": hypothesis_id,
                                "threshold": threshold,
                                "group": group,
                                "signal_date": signal_date,
                                "horizon_days": horizon,
                                **outcome,
                            })
    return pd.DataFrame(rows)


def assign_oos_folds(events: pd.DataFrame, folds: pd.DataFrame) -> pd.DataFrame:
    assigned = []
    for fold in folds.itertuples(index=False):
        subset = events.loc[
            events["signal_date"].between(pd.Timestamp(fold.test_start), pd.Timestamp(fold.test_end))
            & (events["outcome_end"] <= pd.Timestamp(fold.test_end))
        ].copy()
        subset["fold_id"] = fold.fold_id
        assigned.append(subset)
    return pd.concat(assigned, ignore_index=True) if assigned else events.iloc[0:0].copy()


def _holm(rows: list[dict]) -> None:
    ordered = sorted(range(len(rows)), key=lambda index: rows[index]["raw_p_value"])
    running = 0.0
    for rank, index in enumerate(ordered):
        running = max(running, min(1.0, rows[index]["raw_p_value"] * (len(rows) - rank)))
        rows[index]["holm_p_value"] = running


def evaluate_events(events: pd.DataFrame, registry: dict) -> tuple[pd.DataFrame, dict]:
    primary = registry["oos_gate"]["primary_horizon_days"]
    rows: list[dict] = []
    for (hypothesis, threshold), subset in events.loc[
        events["horizon_days"] == primary
    ].groupby(["hypothesis_id", "threshold"]):
        treatment = subset[subset["group"] == "TREATMENT"]
        control = subset[subset["group"] == "CONTROL"]
        fold_gaps = {}
        for fold_id, fold_rows in subset.groupby("fold_id"):
            left = fold_rows[fold_rows["group"] == "TREATMENT"]["forward_excess_return"]
            right = fold_rows[fold_rows["group"] == "CONTROL"]["forward_excess_return"]
            if not left.empty and not right.empty:
                fold_gaps[fold_id] = float(right.median() - left.median())
        p_value = 1.0
        if not treatment.empty and not control.empty:
            p_value = float(mannwhitneyu(
                treatment["forward_excess_return"],
                control["forward_excess_return"],
                alternative="less",
            ).pvalue)
        leave_one_out_gaps = []
        for ticker in sorted(subset["ticker"].unique()):
            reduced = subset[subset["ticker"] != ticker]
            reduced_treatment = reduced[reduced["group"] == "TREATMENT"]["forward_excess_return"]
            reduced_control = reduced[reduced["group"] == "CONTROL"]["forward_excess_return"]
            if not reduced_treatment.empty and not reduced_control.empty:
                leave_one_out_gaps.append(float(reduced_control.median() - reduced_treatment.median()))
        rows.append({
            "hypothesis_id": hypothesis,
            "threshold": float(threshold),
            "treatment_events": len(treatment),
            "control_events": len(control),
            "treatment_tickers": treatment["ticker"].nunique(),
            "test_folds": subset["fold_id"].nunique(),
            "directional_folds": sum(value > 0 for value in fold_gaps.values()),
            "median_excess_gap": (
                float(control["forward_excess_return"].median() - treatment["forward_excess_return"].median())
                if not treatment.empty and not control.empty else None
            ),
            "median_trough_gap": (
                float(control["forward_trough_return"].median() - treatment["forward_trough_return"].median())
                if not treatment.empty and not control.empty else None
            ),
            "median_upside_sacrifice": (
                float(treatment["forward_upside_return"].median()) if not treatment.empty else None
            ),
            "raw_p_value": p_value,
            "fold_gaps": json.dumps(fold_gaps, sort_keys=True),
            "leave_one_ticker_out_sign_holds": bool(
                leave_one_out_gaps and all(value > 0 for value in leave_one_out_gaps)
            ),
        })
    _holm(rows)
    gate = registry["oos_gate"]
    for row in rows:
        row["passed"] = bool(
            row["treatment_events"] >= gate["minimum_events"]
            and row["treatment_tickers"] >= gate["minimum_tickers"]
            and row["test_folds"] >= gate["minimum_test_folds"]
            and row["directional_folds"] >= gate["minimum_directional_folds"]
            and row["holm_p_value"] <= gate["maximum_holm_p_value"]
            and row["median_excess_gap"] is not None and row["median_excess_gap"] > gate["minimum_median_excess_return_gap"]
            and row["median_trough_gap"] is not None and row["median_trough_gap"] > gate["minimum_median_trough_gap"]
            and row["median_upside_sacrifice"] is not None and row["median_upside_sacrifice"] <= gate["maximum_median_upside_sacrifice"]
            and (
                not gate["leave_one_ticker_out_sign_must_hold"]
                or row["leave_one_ticker_out_sign_holds"]
            )
        )
    summary = {
        "registry_version": registry["registry_version"],
        "status": "CONDITIONAL_OOS_PASS" if any(row["passed"] for row in rows) else "NO_ADMITTED_PROFIT_TAKE_EVIDENCE",
        "passing_hypotheses": sorted({row["hypothesis_id"] for row in rows if row["passed"]}),
        "profit_take_authorized": False,
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
    }
    return pd.DataFrame(rows), summary


def _load_price(path: Path) -> pd.DataFrame:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        frame = pd.read_csv(stream, parse_dates=["Date"])
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--folds", type=Path, required=True)
    parser.add_argument("--events-output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    args = parser.parse_args()
    registry, _ = load_registry()
    manifest = json.loads((args.snapshot / "manifest.json").read_text(encoding="utf-8"))
    cache = {ticker: _load_price(args.snapshot / item["path"]) for ticker, item in manifest["files"].items()}
    equity = [ticker for ticker, item in manifest["files"].items() if item["role"] == "EQUITY"]
    events = []
    for ticker in equity:
        sector = TICKER_SECTOR_ETF[ticker]
        events.append(build_events_for_ticker(ticker, cache[ticker], cache[sector], cache["SPY"], registry))
    combined = pd.concat(events, ignore_index=True)
    folds = pd.read_csv(args.folds)
    combined = assign_oos_folds(combined, folds)
    table, summary = evaluate_events(combined, registry)
    args.events_output.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(args.events_output, index=False)
    table.to_csv(args.summary_output.with_suffix(".csv"), index=False)
    args.summary_output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
