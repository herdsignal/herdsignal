"""기업 PASS 최초 -10% 조정의 즉시 5% 추가매수 경제성 기준선을 측정한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

from herd.confirmed_reentry_v1 import _execution, _session_date, _trough_after_entry, load_frames


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json")


def load_protocol(path: Path = PROTOCOL_PATH) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_BASELINE_RESULTS":
        raise ValueError("immediate healthy add baseline must be locked")
    interpretation = protocol.get("interpretation", {})
    if interpretation.get("same_sample_baseline_only") is not True or interpretation.get("pass_does_not_authorize_add_buy") is not True:
        raise ValueError("same-sample baseline boundary weakened")
    if "AUTHORIZE_ADD_BUY_FROM_THIS_SAMPLE" not in protocol.get("forbidden", []):
        raise ValueError("unsafe action authority")
    return protocol


def evaluate_event(event: pd.Series, frame: pd.DataFrame, protocol: dict) -> dict:
    signal = pd.Timestamp(event["signal_date"])
    outcome_end = pd.Timestamp(event["outcome_end"])
    immediate = _execution(frame, signal)
    scheduled_signal = _session_date(frame, signal, 21)
    scheduled = None if scheduled_signal is None else _execution(frame, scheduled_signal)
    terminal_rows = frame[frame["Date"] <= outcome_end]
    if immediate is None or scheduled is None or terminal_rows.empty:
        raise ValueError(f"incomplete baseline path: {event['ticker']} {signal.date()}")
    terminal = float(terminal_rows.iloc[-1]["Adj Close"])
    sleeve = protocol["portfolio"]["sleeve_ratio"]
    result = {
        "ticker": event["ticker"], "signal_date": signal, "fold_id": event["fold_id"],
        "business_state": event["business_state"], "business_month_end": event["business_month_end"],
        "outcome_end": outcome_end, "immediate_entry_date": immediate[0], "immediate_entry_price": immediate[1],
        "scheduled_entry_date": scheduled[0], "scheduled_entry_price": scheduled[1],
    }
    for lane, cost in (("base", protocol["portfolio"]["one_way_cost_base"]), ("stress", protocol["portfolio"]["one_way_cost_stress"])):
        immediate_value = sleeve * (1 - cost) * terminal / immediate[1]
        scheduled_value = sleeve * (1 - cost) * terminal / scheduled[1]
        result[f"immediate_terminal_{lane}"] = immediate_value
        result[f"scheduled_terminal_{lane}"] = scheduled_value
        result[f"uplift_vs_cash_{lane}"] = immediate_value - sleeve
        result[f"uplift_vs_scheduled_{lane}"] = immediate_value - scheduled_value
    trough = _trough_after_entry(frame, immediate[0], immediate[1], outcome_end)
    result["immediate_sleeve_trough"] = trough
    result["immediate_total_position_trough"] = sleeve * trough
    return result


def build_results(source: pd.DataFrame, frames: dict[str, pd.DataFrame], protocol: dict) -> pd.DataFrame:
    required = {"ticker", "signal_date", "fold_id", "business_state", "business_month_end", "outcome_end"}
    if not required.issubset(source):
        raise ValueError("source pullback schema mismatch")
    eligible = source[source["business_state"] == protocol["eligibility"]["business_state"]].copy()
    eligible["signal_date"] = pd.to_datetime(eligible["signal_date"])
    eligible["business_month_end"] = pd.to_datetime(eligible["business_month_end"])
    if (eligible["business_month_end"] >= eligible["signal_date"].dt.to_period("M").dt.start_time).any():
        raise ValueError("same-month business state leaked")
    return pd.DataFrame([evaluate_event(row, frames[row["ticker"]], protocol) for _, row in eligible.iterrows()])


def _holm(items: list[dict]) -> None:
    order = sorted(range(len(items)), key=lambda index: items[index]["raw_p_value"])
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, items[index]["raw_p_value"] * (len(items) - rank)))
        items[index]["holm_p_value"] = running


def evaluate(results: pd.DataFrame, protocol: dict) -> tuple[pd.DataFrame, dict]:
    gate = protocol["baseline_gate"]
    columns = {"CASH": "uplift_vs_cash_stress", "SCHEDULED_21": "uplift_vs_scheduled_stress"}
    rows = []; inference_tests = []
    for comparator, column in columns.items():
        values = results[column].astype(float)
        fold_medians = results.groupby("fold_id")[column].median().to_dict()
        row = {
            "comparison": f"IMMEDIATE_MINUS_{comparator}", "events": len(values),
            "median_total_position_uplift": float(values.median()), "mean_total_position_uplift": float(values.mean()),
            "positive_events": int((values > 0).sum()),
            "fold_medians": fold_medians, "evaluable_folds": len(fold_medians),
            "positive_folds": sum(value > 0 for value in fold_medians.values()),
        }
        results_with_month = results.assign(signal_month=pd.to_datetime(results["signal_date"]).dt.to_period("M").astype(str))
        for unit, key in (("ticker", "ticker"), ("signal_month", "signal_month")):
            grouped = results_with_month.groupby(key)[column].mean()
            test = wilcoxon(grouped, alternative="greater", zero_method="zsplit")
            record = {"row": row, "unit": unit, "observations": len(grouped), "median_uplift": float(grouped.median()), "raw_p_value": float(test.pvalue)}
            inference_tests.append(record)
        rows.append(row)
    _holm(inference_tests)
    for record in inference_tests:
        prefix = record["unit"]
        record["row"][f"{prefix}_observations"] = record["observations"]
        record["row"][f"{prefix}_median_uplift"] = record["median_uplift"]
        record["row"][f"{prefix}_raw_p_value"] = record["raw_p_value"]
        record["row"][f"{prefix}_holm_p_value"] = record["holm_p_value"]
    median_trough = float(results["immediate_total_position_trough"].median())
    tenth_trough = float(results["immediate_total_position_trough"].quantile(0.10))
    for row in rows:
        row["passed"] = bool(
            len(results) >= gate["minimum_events"] and results["ticker"].nunique() >= gate["minimum_tickers"]
            and row["evaluable_folds"] >= gate["minimum_evaluable_folds"]
            and row["positive_folds"] >= gate["minimum_positive_folds_per_comparison"]
            and row["median_total_position_uplift"] > gate["minimum_median_total_position_uplift"]
            and row["ticker_holm_p_value"] <= gate["maximum_cluster_holm_p_value"]
            and row["signal_month_holm_p_value"] <= gate["maximum_cluster_holm_p_value"]
            and median_trough >= gate["minimum_median_total_position_trough"]
            and tenth_trough >= gate["minimum_tenth_percentile_total_position_trough"]
        )
    table = pd.DataFrame(rows)
    passed = int(table["passed"].sum())
    baseline_passed = passed >= gate["required_comparisons_passed"]
    report = {
        "report_version": "HERD_IMMEDIATE_HEALTHY_ADD_BASELINE_V1", "status": "BASELINE_COMPLETE",
        "decision": "PASS_TO_INDEPENDENT_UNSEEN_EQUITY_CONFIRMATION" if baseline_passed else "REJECT_IMMEDIATE_HEALTHY_ADD_BASELINE",
        "eligible_events": len(results), "tickers": results["ticker"].nunique(), "folds": results["fold_id"].nunique(),
        "median_total_position_trough": median_trough, "tenth_percentile_total_position_trough": tenth_trough,
        "comparisons_passed": passed, "same_sample_baseline_only": True, "independent_confirmation_passed": False,
        "add_buy_authorized": False, "five_percent_cycle_executed": False, "operational_action_ratio": 0.0,
        "blind_holdout_access": False, "survivorship_safe": False, "claim_boundary": protocol["claim_boundary"],
    }
    return table, report


def run(protocol_path: Path = PROTOCOL_PATH) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    protocol = load_protocol(protocol_path)
    frames = load_frames(ROOT / protocol["snapshot"])
    results = build_results(pd.read_csv(ROOT / protocol["source_events"]), frames, protocol)
    comparison, report = evaluate(results, protocol)
    return results, comparison, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, required=True); parser.add_argument("--comparison", type=Path, required=True); parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(); events, comparison, report = run(); events.to_csv(args.events, index=False); comparison.to_json(args.comparison, orient="records", indent=2); args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
