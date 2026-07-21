"""시장·섹터 주도 조정과 SEC PIT 기업 비훼손의 상호작용을 OOS fold에서 검증한다."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

from herd.validation_universe import TICKER_SECTOR_ETF


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json")


def load_protocol(path: Path = PROTOCOL_PATH) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_OOS_RESULTS":
        raise ValueError("systematic healthy pullback protocol must be locked")
    forbidden = set(protocol.get("forbidden", []))
    if not {"TREAT_UNKNOWN_AS_PASS", "USE_SAME_MONTH_BUSINESS_SNAPSHOT", "AUTHORIZE_ADD_BUY_FROM_THIS_SAMPLE"}.issubset(forbidden):
        raise ValueError("unsafe business-state or action boundary")
    if len(protocol["primary_contrasts"]) != 2:
        raise ValueError("interaction requires both prelocked contrasts")
    return protocol


def load_frames(snapshot: Path) -> tuple[dict[str, pd.DataFrame], dict]:
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    frames = {}
    for ticker, item in manifest["files"].items():
        with gzip.open(snapshot / item["path"], "rt", encoding="utf-8") as stream:
            frames[ticker] = pd.read_csv(stream, parse_dates=["Date"]).sort_values("Date")
    return frames, manifest


def monthly_pullback_dates(frame: pd.DataFrame, protocol: dict) -> list[pd.Timestamp]:
    rule = protocol["candidate_rule"]
    daily = frame.set_index("Date")["Adj Close"].astype(float)
    drawdown = daily / daily.rolling(rule["drawdown_high_sessions"], min_periods=rule["drawdown_high_sessions"]).max() - 1
    monthly = drawdown.resample("ME").last().dropna()
    dates = []
    armed = True
    last_event_position = -10**9
    for month, value in monthly.items():
        daily_rows = daily.loc[:month]
        if daily_rows.empty:
            continue
        signal = daily_rows.index[-1]
        position = daily.index.get_indexer([signal])[0]
        if value > rule["rearm_drawdown"]:
            armed = True
        if armed and value <= rule["entry_drawdown"] and position - last_event_position >= rule["minimum_sessions_between_events"]:
            dates.append(signal)
            armed = False
            last_event_position = position
    return dates


def decompose(stock: pd.DataFrame, spy: pd.DataFrame, sector: pd.DataFrame, signal: pd.Timestamp, protocol: dict) -> dict:
    def returns(frame: pd.DataFrame, name: str) -> pd.Series:
        close = frame.drop_duplicates("Date").set_index("Date")["Adj Close"].astype(float)
        return np.log(close).diff().rename(name)

    spec = protocol["decomposition"]
    aligned = pd.concat([returns(stock, "stock"), returns(spy, "spy"), returns(sector, "sector")], axis=1, join="inner").dropna()
    history = aligned[aligned.index <= signal].tail(spec["regression_sessions"])
    if len(history) < spec["minimum_regression_sessions"]:
        return {"common_return_63d": np.nan, "residual_return_63d": np.nan, "systematic_fraction": np.nan}
    design = np.column_stack([np.ones(len(history)), history["spy"], history["sector"] - history["spy"]])
    coefficients = np.linalg.lstsq(design, history["stock"].to_numpy(), rcond=None)[0]
    recent = history.tail(spec["attribution_sessions"])
    factor_design = np.column_stack([recent["spy"], recent["sector"] - recent["spy"]])
    # 절편은 시장·섹터가 설명한 수익이 아니다. 종목 고유 기준수익과 함께
    # 잔차 측에 남겨 공통요인 기여를 과대평가하지 않는다.
    common = factor_design @ coefficients[1:]
    residual = recent["stock"].to_numpy() - common
    common_return = float(common.sum())
    residual_return = float(residual.sum())
    common_down = max(-common_return, 0.0)
    residual_down = max(-residual_return, 0.0)
    denominator = common_down + residual_down
    return {
        "common_return_63d": common_return,
        "residual_return_63d": residual_return,
        "systematic_fraction": common_down / denominator if denominator > 0 else np.nan,
    }


def latest_prior_business(business: pd.DataFrame, ticker: str, signal: pd.Timestamp) -> pd.Series | None:
    month_start = signal.to_period("M").start_time
    rows = business[(business["ticker"] == ticker) & (business["month_end"] < month_start)]
    return rows.sort_values("month_end").iloc[-1] if not rows.empty else None


def group_label(state: str, fraction: float, protocol: dict) -> str:
    if state not in {"PASS", "VETO"} or not np.isfinite(fraction):
        return "EXCLUDED_UNKNOWN_OR_MIDDLE"
    spec = protocol["decomposition"]
    source = "SYSTEMATIC" if fraction >= spec["systematic_fraction_high"] else "FIRM_SPECIFIC" if fraction <= spec["systematic_fraction_low"] else "MIDDLE"
    if source == "MIDDLE":
        return "EXCLUDED_UNKNOWN_OR_MIDDLE"
    return ("HEALTHY" if state == "PASS" else "DAMAGED") + "_" + source


def assign_fold(signal: pd.Timestamp, protocol: dict) -> str | None:
    for fold in protocol["test_folds"]:
        if pd.Timestamp(fold["start"]) <= signal <= pd.Timestamp(fold["end"]):
            return fold["id"]
    return None


def outcomes(frame: pd.DataFrame, signal: pd.Timestamp, protocol: dict) -> dict | None:
    close = frame.set_index("Date")["Adj Close"].astype(float)
    position = close.index.searchsorted(signal, side="right") - 1
    horizon = protocol["outcomes"]["horizon_sessions"]
    if position < 0 or position + horizon >= len(close):
        return None
    start = float(close.iloc[position])
    future = close.iloc[position + 1:position + horizon + 1]
    return {"FORWARD_TOTAL_RETURN": float(future.iloc[-1] / start - 1), "FORWARD_TROUGH_RETURN": float(future.min() / start - 1), "outcome_end": future.index[-1]}


def build_events(frames: dict[str, pd.DataFrame], business: pd.DataFrame, protocol: dict) -> pd.DataFrame:
    business = business.copy(); business["month_end"] = pd.to_datetime(business["month_end"])
    rows = []
    equities = [ticker for ticker in business["ticker"].unique() if ticker in frames and ticker in TICKER_SECTOR_ETF]
    for ticker in sorted(equities):
        for signal in monthly_pullback_dates(frames[ticker], protocol):
            fold = assign_fold(signal, protocol)
            result = outcomes(frames[ticker], signal, protocol)
            if fold is None or result is None:
                continue
            fold_end = pd.Timestamp(next(item["end"] for item in protocol["test_folds"] if item["id"] == fold))
            if result["outcome_end"] > fold_end:
                continue
            state_row = latest_prior_business(business, ticker, signal)
            state = "UNKNOWN" if state_row is None else state_row["guard_state"]
            decomposition = decompose(frames[ticker], frames["SPY"], frames[TICKER_SECTOR_ETF[ticker]], signal, protocol)
            rows.append({"ticker": ticker, "signal_date": signal, "fold_id": fold, "business_state": state, "business_month_end": None if state_row is None else state_row["month_end"], **decomposition, "group": group_label(state, decomposition["systematic_fraction"], protocol), **result})
    return pd.DataFrame(rows)


def _holm(rows: list[dict]) -> None:
    order = sorted(range(len(rows)), key=lambda index: rows[index]["raw_p_value"])
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, rows[index]["raw_p_value"] * (len(rows) - rank)))
        rows[index]["holm_p_value"] = running


def evaluate(events: pd.DataFrame, protocol: dict) -> tuple[pd.DataFrame, dict]:
    gate = protocol["adoption_gate"]
    rows = []
    for contrast in protocol["primary_contrasts"]:
        for outcome in protocol["outcomes"]["primary"]:
            treatment = events[events["group"] == contrast["treatment"]]
            control = events[events["group"] == contrast["control"]]
            left, right = treatment[outcome].dropna(), control[outcome].dropna()
            if len(left) and len(right):
                test = mannwhitneyu(left, right, alternative="greater")
                effect = 2 * float(test.statistic) / (len(left) * len(right)) - 1
                p_value = float(test.pvalue)
            else:
                effect, p_value = np.nan, 1.0
            fold_effects = []
            for fold in protocol["test_folds"]:
                a = treatment[treatment["fold_id"] == fold["id"]][outcome].dropna()
                b = control[control["fold_id"] == fold["id"]][outcome].dropna()
                fold_effect = None if len(a) < 5 or len(b) < 5 else 2 * float(mannwhitneyu(a, b).statistic) / (len(a) * len(b)) - 1
                fold_effects.append({"fold_id": fold["id"], "effect": fold_effect})
            rows.append({"contrast": contrast["id"], "outcome": outcome, "treatment": contrast["treatment"], "control": contrast["control"], "treatment_events": len(left), "control_events": len(right), "treatment_tickers": treatment["ticker"].nunique(), "control_tickers": control["ticker"].nunique(), "rank_biserial": effect, "raw_p_value": p_value, "fold_effects": fold_effects, "evaluable_folds": sum(item["effect"] is not None for item in fold_effects), "directional_folds": sum(item["effect"] is not None and item["effect"] > 0 for item in fold_effects)})
    _holm(rows)
    for row in rows:
        row["passed"] = bool(row["treatment_events"] >= gate["minimum_events_per_side"] and row["control_events"] >= gate["minimum_events_per_side"] and row["treatment_tickers"] >= gate["minimum_tickers_per_side"] and row["control_tickers"] >= gate["minimum_tickers_per_side"] and row["evaluable_folds"] >= gate["minimum_evaluable_folds"] and row["directional_folds"] >= gate["minimum_directional_folds"] and row["rank_biserial"] >= gate["minimum_rank_biserial"] and row["holm_p_value"] <= gate["maximum_holm_p_value"])
    table = pd.DataFrame(rows)
    passed_by_contrast = table.groupby("contrast")["passed"].sum().to_dict()
    accepted = sum(value >= gate["required_passed_outcomes_per_contrast"] for value in passed_by_contrast.values()) >= gate["required_passed_contrasts"]
    report = {"report_version": "HERD_SYSTEMATIC_HEALTHY_PULLBACK_V1", "status": "OOS_COMPLETE", "decision": "PASS_TO_5_PERCENT_CYCLE_CONFIRMATION" if accepted else "REJECT_OR_INSUFFICIENT_INTERACTION_EVIDENCE", "events": len(events), "group_counts": events["group"].value_counts().to_dict(), "passed_outcomes_by_contrast": passed_by_contrast, "all_primary_contrasts_passed": accepted, "claim_boundary": protocol["claim_boundary"], "survivorship_safe": False, "add_buy_authorized": False, "operational_action_ratio": 0.0, "blind_holdout_access": False}
    return table, report


def run(protocol_path: Path = PROTOCOL_PATH) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    protocol = load_protocol(protocol_path)
    frames, _ = load_frames(ROOT / protocol["snapshot"])
    events = build_events(frames, pd.read_csv(ROOT / protocol["business_features"]), protocol)
    comparison, report = evaluate(events, protocol)
    return events, comparison, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, required=True); parser.add_argument("--comparison", type=Path, required=True); parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(); events, comparison, report = run()
    events.to_csv(args.events, index=False); comparison.to_json(args.comparison, orient="records", indent=2)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
