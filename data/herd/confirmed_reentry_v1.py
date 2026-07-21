"""기업 상태가 정상인 조정에서 하락 정지·상대강도 회복 확인 후 5% 재진입을 검증한다."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

from herd.validation_universe import TICKER_SECTOR_ETF


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json")


def load_protocol(path: Path = PROTOCOL_PATH) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_OOS_RESULTS":
        raise ValueError("confirmed reentry protocol must be locked")
    forbidden = set(protocol.get("forbidden", []))
    required = {"USE_CONFIRMATION_DAY_OPEN_FOR_EXECUTION", "EXCLUDE_UNCONFIRMED_FROM_STRATEGY_RETURN", "AUTHORIZE_REENTRY_FROM_THIS_SAMPLE"}
    if not required.issubset(forbidden):
        raise ValueError("confirmed reentry safety boundary weakened")
    if protocol["portfolio"]["sleeve_ratio"] != 0.05:
        raise ValueError("only the prelocked five-percent sleeve is allowed")
    return protocol


def load_frames(snapshot: Path) -> dict[str, pd.DataFrame]:
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    frames = {}
    for ticker, item in manifest["files"].items():
        with gzip.open(snapshot / item["path"], "rt", encoding="utf-8") as stream:
            frame = pd.read_csv(stream, parse_dates=["Date"]).sort_values("Date").reset_index(drop=True)
        factor = frame["Adj Close"].astype(float) / frame["Close"].astype(float)
        frame["Adjusted Open"] = frame["Open"].astype(float) * factor
        frames[ticker] = frame
    return frames


def _aligned_closes(stock: pd.DataFrame, spy: pd.DataFrame, sector: pd.DataFrame) -> pd.DataFrame:
    def close(frame: pd.DataFrame, name: str) -> pd.Series:
        return frame.drop_duplicates("Date").set_index("Date")["Adj Close"].astype(float).rename(name)
    return pd.concat([close(stock, "stock"), close(spy, "spy"), close(sector, "sector")], axis=1, join="inner").dropna().sort_index()


def find_confirmation(stock: pd.DataFrame, spy: pd.DataFrame, sector: pd.DataFrame, signal: pd.Timestamp, protocol: dict) -> dict:
    spec = protocol["confirmation"]
    aligned = _aligned_closes(stock, spy, sector)
    signal_position = aligned.index.searchsorted(signal, side="right") - 1
    if signal_position < spec["relative_return_sessions"]:
        return {"confirmation_date": pd.NaT, "confirmation_wait_sessions": np.nan}
    end = min(signal_position + spec["maximum_wait_sessions"], len(aligned) - 2)
    episode_low_position = signal_position
    for position in range(signal_position + 1, end + 1):
        if aligned["stock"].iloc[position] < aligned["stock"].iloc[episode_low_position]:
            episode_low_position = position
        sessions_since_low = position - episode_low_position
        recovery = aligned["stock"].iloc[position] / aligned["stock"].iloc[episode_low_position] - 1
        lookback = spec["relative_return_sessions"]
        stock_return = aligned["stock"].iloc[position] / aligned["stock"].iloc[position - lookback] - 1
        spy_return = aligned["spy"].iloc[position] / aligned["spy"].iloc[position - lookback] - 1
        sector_return = aligned["sector"].iloc[position] / aligned["sector"].iloc[position - lookback] - 1
        if sessions_since_low >= spec["minimum_sessions_since_episode_low"] and recovery >= spec["minimum_recovery_from_episode_low"] and stock_return > spy_return and stock_return > sector_return:
            return {"confirmation_date": aligned.index[position], "confirmation_wait_sessions": position - signal_position}
    return {"confirmation_date": pd.NaT, "confirmation_wait_sessions": np.nan}


def _execution(frame: pd.DataFrame, after: pd.Timestamp) -> tuple[pd.Timestamp, float] | None:
    rows = frame[frame["Date"] > after]
    if rows.empty:
        return None
    row = rows.iloc[0]
    return pd.Timestamp(row["Date"]), float(row["Adjusted Open"])


def _session_date(frame: pd.DataFrame, signal: pd.Timestamp, offset: int) -> pd.Timestamp | None:
    dates = frame["Date"].drop_duplicates().sort_values().reset_index(drop=True)
    position = dates.searchsorted(signal, side="right") - 1
    target = position + offset
    return None if position < 0 or target >= len(dates) else pd.Timestamp(dates.iloc[target])


def _trough_after_entry(frame: pd.DataFrame, entry_date: pd.Timestamp, entry_price: float, outcome_end: pd.Timestamp) -> float:
    future = frame[(frame["Date"] >= entry_date) & (frame["Date"] <= outcome_end)]["Adj Close"].astype(float)
    return np.nan if future.empty else float(future.min() / entry_price - 1)


def evaluate_event(event: pd.Series, frames: dict[str, pd.DataFrame], protocol: dict) -> dict:
    ticker = event["ticker"]; stock = frames[ticker]
    signal = pd.Timestamp(event["signal_date"]); outcome_end = pd.Timestamp(event["outcome_end"])
    confirmation = find_confirmation(stock, frames["SPY"], frames[TICKER_SECTOR_ETF[ticker]], signal, protocol)
    immediate = _execution(stock, signal)
    wait_signal = _session_date(stock, signal, 21)
    fixed_wait = None if wait_signal is None else _execution(stock, wait_signal)
    confirmed = None if pd.isna(confirmation["confirmation_date"]) else _execution(stock, confirmation["confirmation_date"])
    terminal_rows = stock[stock["Date"] <= outcome_end]
    if immediate is None or fixed_wait is None or terminal_rows.empty:
        raise ValueError(f"incomplete execution path: {ticker} {signal.date()}")
    terminal = float(terminal_rows.iloc[-1]["Adj Close"])
    sleeve = protocol["portfolio"]["sleeve_ratio"]

    def terminal_value(execution: tuple[pd.Timestamp, float] | None, cost: float) -> float:
        return sleeve if execution is None else sleeve * (1 - cost) * terminal / execution[1]

    result = {**event.to_dict(), **confirmation, "confirmed": confirmed is not None, "immediate_entry_date": immediate[0], "immediate_entry_price": immediate[1], "fixed_wait_entry_date": fixed_wait[0], "fixed_wait_entry_price": fixed_wait[1], "confirmed_entry_date": pd.NaT if confirmed is None else confirmed[0], "confirmed_entry_price": np.nan if confirmed is None else confirmed[1]}
    for lane, cost in (("base", protocol["portfolio"]["one_way_cost_base"]), ("stress", protocol["portfolio"]["one_way_cost_stress"])):
        strategy = terminal_value(confirmed, cost); immediate_value = terminal_value(immediate, cost); fixed_value = terminal_value(fixed_wait, cost)
        result[f"strategy_terminal_{lane}"] = strategy
        result[f"uplift_vs_immediate_{lane}"] = strategy - immediate_value
        result[f"uplift_vs_fixed_wait_{lane}"] = strategy - fixed_value
    result["confirmed_entry_trough"] = np.nan if confirmed is None else _trough_after_entry(stock, confirmed[0], confirmed[1], outcome_end)
    result["immediate_entry_trough"] = _trough_after_entry(stock, immediate[0], immediate[1], outcome_end)
    result["entry_drawdown_improvement"] = np.nan if confirmed is None else result["confirmed_entry_trough"] - result["immediate_entry_trough"]
    return result


def build_results(source: pd.DataFrame, frames: dict[str, pd.DataFrame], protocol: dict) -> pd.DataFrame:
    required = {"ticker", "signal_date", "fold_id", "business_state", "business_month_end", "outcome_end"}
    if not required.issubset(source):
        raise ValueError("source pullback event schema mismatch")
    source = source[source["business_state"] == protocol["eligibility"]["business_state"]].copy()
    source["signal_date"] = pd.to_datetime(source["signal_date"]); source["business_month_end"] = pd.to_datetime(source["business_month_end"])
    if (source["business_month_end"] >= source["signal_date"].dt.to_period("M").dt.start_time).any():
        raise ValueError("same-month SEC business state leaked into reentry study")
    return pd.DataFrame([evaluate_event(row, frames, protocol) for _, row in source.iterrows()])


def _holm(rows: list[dict]) -> None:
    order = sorted(range(len(rows)), key=lambda index: rows[index]["raw_p_value"])
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, rows[index]["raw_p_value"] * (len(rows) - rank)))
        rows[index]["holm_p_value"] = running


def evaluate(results: pd.DataFrame, protocol: dict) -> tuple[pd.DataFrame, dict]:
    gate = protocol["adoption_gate"]; rows = []
    for comparator in ("immediate", "fixed_wait"):
        values = results[f"uplift_vs_{comparator}_stress"].astype(float)
        test = wilcoxon(values, alternative="greater", zero_method="zsplit")
        fold_medians = results.groupby("fold_id")[f"uplift_vs_{comparator}_stress"].median().to_dict()
        rows.append({"comparator": comparator.upper(), "events": len(values), "median_total_position_uplift": float(values.median()), "mean_total_position_uplift": float(values.mean()), "positive_events": int((values > 0).sum()), "raw_p_value": float(test.pvalue), "fold_medians": fold_medians, "evaluable_folds": len(fold_medians), "positive_uplift_folds": sum(value > 0 for value in fold_medians.values())})
    _holm(rows)
    rate = float(results["confirmed"].mean()); drawdown = float(results.loc[results["confirmed"], "entry_drawdown_improvement"].median())
    for row in rows:
        row["passed"] = bool(len(results) >= gate["minimum_eligible_events"] and results["ticker"].nunique() >= gate["minimum_tickers"] and gate["minimum_confirmation_rate"] <= rate <= gate["maximum_confirmation_rate"] and row["evaluable_folds"] >= gate["minimum_evaluable_folds"] and row["positive_uplift_folds"] >= gate["minimum_positive_uplift_folds_per_comparator"] and row["median_total_position_uplift"] > gate["minimum_median_total_position_uplift"] and drawdown >= gate["minimum_confirmed_entry_drawdown_improvement"] and row["holm_p_value"] <= gate["maximum_holm_p_value"])
    table = pd.DataFrame(rows); accepted = int(table["passed"].sum()) >= gate["required_comparators_passed"]
    report = {"report_version": "HERD_CONFIRMED_REENTRY_V1", "status": "OOS_COMPLETE", "decision": "PASS_TO_INDEPENDENT_CONFIRMATION" if accepted else "REJECT_CONFIRMED_REENTRY_RULE", "eligible_events": len(results), "tickers": results["ticker"].nunique(), "confirmed_events": int(results["confirmed"].sum()), "confirmation_rate": rate, "median_confirmation_wait_sessions": float(results.loc[results["confirmed"], "confirmation_wait_sessions"].median()) if results["confirmed"].any() else None, "median_confirmed_entry_drawdown_improvement": drawdown, "comparators_passed": int(table["passed"].sum()), "reentry_authorized": False, "five_percent_cycle_executed": False, "operational_action_ratio": 0.0, "blind_holdout_access": False, "survivorship_safe": False, "claim_boundary": protocol["claim_boundary"]}
    return table, report


def run(protocol_path: Path = PROTOCOL_PATH) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    protocol = load_protocol(protocol_path); frames = load_frames(ROOT / protocol["snapshot"])
    results = build_results(pd.read_csv(ROOT / protocol["source_events"]), frames, protocol)
    comparison, report = evaluate(results, protocol)
    return results, comparison, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--events", type=Path, required=True); parser.add_argument("--comparison", type=Path, required=True); parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(); events, comparison, report = run(); events.to_csv(args.events, index=False); comparison.to_json(args.comparison, orient="records", indent=2); args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
