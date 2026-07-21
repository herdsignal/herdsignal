"""Rush 이후 희소한 일간 추세 훼손에서 5% 부분 익절의 경제성을 검증한다."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json")


def load_protocol(path: Path = PROTOCOL_PATH) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_RESULTS":
        raise ValueError("Rush damage profit-take protocol must be locked")
    if protocol["portfolio"]["profit_take_ratio"] != 0.05:
        raise ValueError("only a five-percent profit take is allowed")
    required = {"HIGH_HERD_ALONE_CREATES_SELL", "USE_DAMAGE_DAY_OPEN", "DROP_UNTRIGGERED_EPISODES", "AUTHORIZE_PROFIT_TAKE_FROM_THIS_SAMPLE"}
    if not required.issubset(protocol.get("forbidden", [])):
        raise ValueError("Rush damage action boundary weakened")
    return protocol


def load_frames(snapshot: Path, tickers: set[str]) -> dict[str, pd.DataFrame]:
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    frames = {}
    for ticker in sorted(tickers):
        item = manifest["files"][ticker]
        with gzip.open(snapshot / item["path"], "rt", encoding="utf-8") as stream:
            frame = pd.read_csv(stream, parse_dates=["Date"]).sort_values("Date").reset_index(drop=True)
        factor = frame["Adj Close"].astype(float) / frame["Close"].astype(float)
        frame["Adjusted Open"] = frame["Open"].astype(float) * factor
        frames[ticker] = frame
    return frames


def safe_events(path: Path, protocol: dict) -> pd.DataFrame:
    source = pd.read_csv(path)
    columns = protocol["safe_source_columns"]
    if not set(columns).issubset(source):
        raise ValueError("independent Rush source schema mismatch")
    events = source[columns].copy()
    events["signal_date"] = pd.to_datetime(events["signal_date"])
    events["last_observed_session"] = pd.to_datetime(events["last_observed_session"])
    if (events["last_observed_session"] > events["signal_date"]).any():
        raise ValueError("post-signal source observation")
    return events


def _aligned(stock: pd.DataFrame, spy: pd.DataFrame, sector: pd.DataFrame) -> pd.DataFrame:
    def close(frame: pd.DataFrame, name: str) -> pd.Series:
        return frame.drop_duplicates("Date").set_index("Date")["Adj Close"].astype(float).rename(name)
    return pd.concat([close(stock, "stock"), close(spy, "spy"), close(sector, "sector")], axis=1, join="inner").dropna().sort_index()


def find_damage(stock: pd.DataFrame, spy: pd.DataFrame, sector: pd.DataFrame, signal: pd.Timestamp, protocol: dict) -> dict:
    spec = protocol["damage_confirmation"]
    aligned = _aligned(stock, spy, sector)
    signal_position = aligned.index.searchsorted(signal, side="right") - 1
    warmup = max(spec["prior_low_sessions"], spec["moving_average_sessions"], spec["relative_return_sessions"])
    if signal_position < warmup:
        return {"damage_date": pd.NaT, "damage_wait_sessions": np.nan}
    end = min(signal_position + spec["maximum_wait_sessions"], len(aligned) - 2)
    for position in range(signal_position + 1, end + 1):
        close = aligned["stock"].iloc[position]
        prior_low = aligned["stock"].iloc[position - spec["prior_low_sessions"]:position].min()
        moving_average = aligned["stock"].iloc[position - spec["moving_average_sessions"] + 1:position + 1].mean()
        lookback = spec["relative_return_sessions"]
        stock_return = close / aligned["stock"].iloc[position - lookback] - 1
        spy_return = aligned["spy"].iloc[position] / aligned["spy"].iloc[position - lookback] - 1
        sector_return = aligned["sector"].iloc[position] / aligned["sector"].iloc[position - lookback] - 1
        if close < prior_low and close < moving_average and stock_return < spy_return and stock_return < sector_return:
            return {"damage_date": aligned.index[position], "damage_wait_sessions": position - signal_position}
    return {"damage_date": pd.NaT, "damage_wait_sessions": np.nan}


def _execution(frame: pd.DataFrame, after: pd.Timestamp) -> tuple[pd.Timestamp, float] | None:
    rows = frame[frame["Date"] > after]
    if rows.empty:
        return None
    row = rows.iloc[0]
    return pd.Timestamp(row["Date"]), float(row["Adjusted Open"])


def _session(frame: pd.DataFrame, signal: pd.Timestamp, offset: int) -> pd.Timestamp | None:
    dates = frame["Date"].drop_duplicates().sort_values().reset_index(drop=True)
    position = dates.searchsorted(signal, side="right") - 1
    target = position + offset
    return None if position < 0 or target >= len(dates) else pd.Timestamp(dates.iloc[target])


def _path_metrics(frame: pd.DataFrame, signal: pd.Timestamp, sale: tuple[pd.Timestamp, float] | None, protocol: dict, cost: float) -> dict | None:
    close = frame.set_index("Date")["Adj Close"].astype(float)
    position = close.index.searchsorted(signal, side="right") - 1
    horizon = protocol["portfolio"]["outcome_sessions_after_rush"]
    if position < 0 or position + horizon >= len(close):
        return None
    initial = float(close.iloc[position]); future = close.iloc[position + 1:position + horizon + 1]
    bh_terminal = float(future.iloc[-1] / initial)
    bh_path = future / initial
    if sale is None:
        return {"terminal": bh_terminal, "uplift_vs_bh": 0.0, "trough_improvement": 0.0, "outcome_end": future.index[-1]}
    ratio = protocol["portfolio"]["profit_take_ratio"]
    cash = ratio * sale[1] * (1 - cost)
    strategy_path = ((1 - ratio) * future + cash) / initial
    return {"terminal": float(strategy_path.iloc[-1]), "uplift_vs_bh": float(strategy_path.iloc[-1] - bh_terminal), "trough_improvement": float(strategy_path.min() - bh_path.min()), "outcome_end": future.index[-1]}


def evaluate_event(event: pd.Series, frames: dict[str, pd.DataFrame], protocol: dict) -> dict:
    ticker = event["ticker"]; stock = frames[ticker]; signal = pd.Timestamp(event["signal_date"])
    damage = find_damage(stock, frames["SPY"], frames[event["sector_etf"]], signal, protocol)
    damage_sale = None if pd.isna(damage["damage_date"]) else _execution(stock, damage["damage_date"])
    scheduled_signal = _session(stock, signal, 21)
    scheduled_sale = None if scheduled_signal is None else _execution(stock, scheduled_signal)
    result = {**event.to_dict(), **damage, "damage_triggered": damage_sale is not None, "damage_execution_date": pd.NaT if damage_sale is None else damage_sale[0], "damage_execution_price": np.nan if damage_sale is None else damage_sale[1], "scheduled_execution_date": pd.NaT if scheduled_sale is None else scheduled_sale[0], "scheduled_execution_price": np.nan if scheduled_sale is None else scheduled_sale[1]}
    for lane, cost in (("base", protocol["portfolio"]["one_way_cost_base"]), ("stress", protocol["portfolio"]["one_way_cost_stress"])):
        damage_metrics = _path_metrics(stock, signal, damage_sale, protocol, cost)
        scheduled_metrics = _path_metrics(stock, signal, scheduled_sale, protocol, cost)
        if damage_metrics is None or scheduled_metrics is None:
            raise ValueError(f"incomplete Rush outcome: {ticker} {signal.date()}")
        result[f"uplift_vs_buy_hold_{lane}"] = damage_metrics["uplift_vs_bh"]
        result[f"uplift_vs_scheduled_{lane}"] = damage_metrics["terminal"] - scheduled_metrics["terminal"]
        result[f"triggered_trough_improvement_{lane}"] = damage_metrics["trough_improvement"] if damage_sale is not None else np.nan
        result["outcome_end"] = damage_metrics["outcome_end"]
    return result


def assign_fold(date: pd.Timestamp, protocol: dict) -> str:
    for fold in protocol["folds"]:
        if pd.Timestamp(fold["start"]) <= date <= pd.Timestamp(fold["end"]):
            return fold["id"]
    raise ValueError(f"Rush event outside folds: {date}")


def build_results(events: pd.DataFrame, frames: dict[str, pd.DataFrame], protocol: dict) -> pd.DataFrame:
    rows = []
    for _, event in events.iterrows():
        result = evaluate_event(event, frames, protocol)
        result["fold_id"] = assign_fold(pd.Timestamp(event["signal_date"]), protocol)
        rows.append(result)
    return pd.DataFrame(rows)


def _holm(items: list[dict]) -> None:
    order = sorted(range(len(items)), key=lambda index: items[index]["raw_p_value"]); running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, items[index]["raw_p_value"] * (len(items) - rank))); items[index]["holm_p_value"] = running


def evaluate(results: pd.DataFrame, protocol: dict) -> tuple[pd.DataFrame, dict]:
    gate = protocol["adoption_gate"]; rows = []; inference = []
    columns = {"BUY_AND_HOLD": "uplift_vs_buy_hold_stress", "SCHEDULED_TRIM_21": "uplift_vs_scheduled_stress"}
    with_month = results.assign(signal_month=pd.to_datetime(results["signal_date"]).dt.to_period("M").astype(str))
    for comparator, column in columns.items():
        values = results[column].astype(float); fold_medians = results.groupby("fold_id")[column].median().to_dict()
        row = {"comparison": f"DAMAGE_RULE_MINUS_{comparator}", "episodes": len(values), "median_total_position_uplift": float(values.median()), "mean_total_position_uplift": float(values.mean()), "positive_episodes": int((values > 0).sum()), "fold_medians": fold_medians, "evaluable_folds": len(fold_medians), "positive_folds": sum(value > 0 for value in fold_medians.values())}
        for unit in ("ticker", "signal_month"):
            grouped = with_month.groupby(unit)[column].mean(); test = wilcoxon(grouped, alternative="greater", zero_method="zsplit")
            inference.append({"row": row, "unit": unit, "observations": len(grouped), "median_uplift": float(grouped.median()), "raw_p_value": float(test.pvalue)})
        rows.append(row)
    _holm(inference)
    for item in inference:
        prefix = item["unit"]; item["row"][f"{prefix}_observations"] = item["observations"]; item["row"][f"{prefix}_median_uplift"] = item["median_uplift"]; item["row"][f"{prefix}_raw_p_value"] = item["raw_p_value"]; item["row"][f"{prefix}_holm_p_value"] = item["holm_p_value"]
    rate = float(results["damage_triggered"].mean()); triggered = results[results["damage_triggered"]]
    years = (pd.to_datetime(results["signal_date"]).max() - pd.to_datetime(results["signal_date"]).min()).days / 365.2425
    annual = triggered.groupby("ticker").size().reindex(results["ticker"].unique(), fill_value=0) / years
    trough = float(triggered["triggered_trough_improvement_stress"].median()) if not triggered.empty else np.nan
    for row in rows:
        row["passed"] = bool(len(results) >= gate["minimum_episodes"] and results["ticker"].nunique() >= gate["minimum_tickers"] and gate["minimum_damage_rate"] <= rate <= gate["maximum_damage_rate"] and annual.median() <= gate["maximum_median_annual_damage_events_per_ticker"] and row["evaluable_folds"] >= gate["minimum_evaluable_folds"] and row["positive_folds"] >= gate["minimum_positive_folds_per_comparison"] and row["median_total_position_uplift"] > gate["minimum_median_total_position_uplift"] and trough >= gate["minimum_median_triggered_trough_improvement"] and row["ticker_holm_p_value"] <= gate["maximum_cluster_holm_p_value"] and row["signal_month_holm_p_value"] <= gate["maximum_cluster_holm_p_value"])
    table = pd.DataFrame(rows); passed = int(table["passed"].sum()); accepted = passed >= gate["required_comparisons_passed"]
    report = {"report_version": "HERD_RUSH_DAMAGE_PROFIT_TAKE_V1", "status": "OOS_COMPLETE", "decision": "PASS_TO_NEW_INDEPENDENT_CONFIRMATION" if accepted else "REJECT_RUSH_DAMAGE_PROFIT_TAKE", "episodes": len(results), "tickers": results["ticker"].nunique(), "damage_events": int(triggered.shape[0]), "damage_rate": rate, "median_damage_wait_sessions": float(triggered["damage_wait_sessions"].median()) if not triggered.empty else None, "median_annual_damage_events_per_ticker": float(annual.median()), "median_triggered_trough_improvement": trough, "comparisons_passed": passed, "profit_take_authorized": False, "five_percent_cash_creation_authorized": False, "operational_action_ratio": 0.0, "blind_holdout_access": False, "survivorship_safe": False, "claim_boundary": protocol["claim_boundary"]}
    return table, report


def run(protocol_path: Path = PROTOCOL_PATH) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    protocol = load_protocol(protocol_path); events = safe_events(ROOT / protocol["source_events"], protocol)
    required = set(events["ticker"]) | {"SPY"} | set(events["sector_etf"]); frames = load_frames(ROOT / protocol["snapshot"], required)
    results = build_results(events, frames, protocol); comparison, report = evaluate(results, protocol)
    return results, comparison, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--events", type=Path, required=True); parser.add_argument("--comparison", type=Path, required=True); parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(); events, comparison, report = run(); events.to_csv(args.events, index=False); comparison.to_json(args.comparison, orient="records", indent=2); args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
