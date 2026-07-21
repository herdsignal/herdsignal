"""Rush episode의 5% 익절·재진입 이론/제약 상한을 측정한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from herd.cycle_value_protocol_v1 import load_protocol
from herd.long_price_snapshot import verify_snapshot


def _split_multipliers(frame: pd.DataFrame, sale_position: int, end_position: int) -> np.ndarray:
    splits = frame["Stock Splits"].iloc[sale_position:end_position + 1].astype(float).to_numpy()
    factors = np.where(splits > 0, splits, 1.0)
    factors[0] = 1.0
    return np.cumprod(factors)


def _scenario(
    future: pd.DataFrame,
    *,
    sale_open: float,
    split_multipliers: np.ndarray,
    fraction: float,
    fee: float,
    slippage: float,
    minimum_discount: float,
    minimum_run: int,
    maximum_advance: float,
) -> dict:
    sale_execution = sale_open * (1.0 - slippage)
    proceeds_per_sold_share = sale_execution * (1.0 - fee)
    equivalent_opens = future["Open"].astype(float).to_numpy() * split_multipliers
    all_in_reentry = equivalent_opens * (1.0 + slippage) * (1.0 + fee)
    share_delta = proceeds_per_sold_share / all_in_reentry - 1.0

    theoretical_index = int(np.argmin(all_in_reentry))
    theoretical_delta = float(share_delta[theoretical_index])
    theoretical_available = theoretical_delta > 0.0

    discount_mask = share_delta >= minimum_discount
    qualifying_starts = []
    for index in range(0, len(discount_mask) - minimum_run + 1):
        if not discount_mask[index:index + minimum_run].all():
            continue
        prior = equivalent_opens[:index + 1] / sale_open - 1.0
        pre_advance = float(prior.max()) if len(prior) else 0.0
        if pre_advance <= maximum_advance:
            qualifying_starts.append(index)
    constrained_index = min(qualifying_starts, key=lambda index: all_in_reentry[index]) if qualifying_starts else None
    constrained_delta = float(share_delta[constrained_index]) if constrained_index is not None else 0.0

    def fields(prefix: str, index: int | None, delta: float, available: bool) -> dict:
        return {
            f"{prefix}_available": bool(available),
            f"{prefix}_reentry_date": future["Date"].iloc[index].date().isoformat() if index is not None and available else None,
            f"{prefix}_reentry_equivalent_price": float(equivalent_opens[index]) if index is not None and available else None,
            f"{prefix}_time_to_reentry_sessions": int(index + 1) if index is not None and available else None,
            f"{prefix}_sleeve_share_delta_rate": delta if available else 0.0,
            f"{prefix}_total_position_terminal_uplift": fraction * delta if available else 0.0,
        }

    constrained_pre_advance = None
    if constrained_index is not None:
        constrained_pre_advance = float((equivalent_opens[:constrained_index + 1] / sale_open - 1.0).max())
    return {
        "sale_execution_price": float(sale_execution),
        "net_proceeds_per_sold_share": float(proceeds_per_sold_share),
        "days_below_net_discount": int(discount_mask.sum()),
        "constrained_pre_reentry_max_advance": constrained_pre_advance,
        **fields("theoretical", theoretical_index, theoretical_delta, theoretical_available),
        **fields("constrained", constrained_index, constrained_delta, constrained_index is not None),
    }


def measure_episode(frame: pd.DataFrame, signal_date: pd.Timestamp, protocol: dict) -> dict | None:
    prices = frame.copy().sort_values("Date").reset_index(drop=True)
    prices["Date"] = pd.to_datetime(prices["Date"])
    signal_position = prices["Date"].searchsorted(pd.Timestamp(signal_date), side="right") - 1
    sale_position = signal_position + 1
    horizon = protocol["input"]["horizon_sessions_after_signal"]
    end_position = signal_position + horizon
    if signal_position < 0 or sale_position >= len(prices) or end_position >= len(prices):
        return None
    sale_open = float(prices["Open"].iloc[sale_position])
    future = prices.iloc[sale_position + 1:end_position + 1].copy().reset_index(drop=True)
    multipliers = _split_multipliers(prices, sale_position, end_position)[1:]
    execution = protocol["execution"]
    constrained = protocol["ceilings"]["constrained_oracle"]
    common = {
        "future": future,
        "sale_open": sale_open,
        "split_multipliers": multipliers,
        "fraction": execution["profit_take_fraction"],
        "minimum_discount": constrained["minimum_net_discount_from_sale_execution"],
        "minimum_run": constrained["minimum_consecutive_qualifying_sessions"],
        "maximum_advance": constrained["maximum_advance_before_reentry"],
    }
    base = _scenario(
        **common,
        fee=execution["base_one_way_fee_rate"],
        slippage=execution["base_one_way_slippage_rate"],
    )
    stress = _scenario(
        **common,
        fee=execution["stress_one_way_fee_rate"],
        slippage=execution["stress_one_way_slippage_rate"],
    )
    terminal_close = float(prices["Close"].iloc[end_position])
    terminal_split = float(_split_multipliers(prices, sale_position, end_position)[-1])
    return {
        "sale_date": prices["Date"].iloc[sale_position].date().isoformat(),
        "sale_reference_open": sale_open,
        "outcome_end": prices["Date"].iloc[end_position].date().isoformat(),
        "no_action_terminal_wealth_per_sale_date_share": terminal_close * terminal_split,
        **{f"base_{key}": value for key, value in base.items()},
        **{f"stress_{key}": value for key, value in stress.items()},
    }


def summarize_scenario(events: pd.DataFrame, prefix: str, protocol: dict) -> dict:
    constrained = events[f"{prefix}_constrained_available"]
    conditional = events.loc[constrained, f"{prefix}_constrained_sleeve_share_delta_rate"]
    result = {
        "evaluable_episodes": int(len(events)),
        "theoretical_opportunity_rate": float(events[f"{prefix}_theoretical_available"].mean()),
        "constrained_opportunity_rate": float(constrained.mean()),
        "mean_total_position_terminal_uplift": float(events[f"{prefix}_constrained_total_position_terminal_uplift"].mean()),
        "median_conditional_sleeve_share_delta_rate": float(conditional.median()) if len(conditional) else None,
        "median_time_to_reentry_sessions": float(events.loc[constrained, f"{prefix}_constrained_time_to_reentry_sessions"].median()) if constrained.any() else None,
        "median_days_below_net_discount": float(events[f"{prefix}_days_below_net_discount"].median()),
    }
    gate = protocol["economic_feasibility_gate"]
    result["gate_passed"] = bool(
        result["evaluable_episodes"] >= gate["minimum_evaluable_episodes"]
        and result["constrained_opportunity_rate"] >= gate["minimum_constrained_opportunity_rate"]
        and result["mean_total_position_terminal_uplift"] >= gate["minimum_mean_total_position_terminal_uplift"]
        and result["median_conditional_sleeve_share_delta_rate"] is not None
        and result["median_conditional_sleeve_share_delta_rate"] >= gate["minimum_median_conditional_sleeve_share_delta_rate"]
    )
    return result


def run(snapshot: Path, episodes_path: Path) -> tuple[pd.DataFrame, dict]:
    protocol = load_protocol()
    manifest = verify_snapshot(snapshot)
    episodes = pd.read_csv(episodes_path)
    episodes["last_observed_session"] = pd.to_datetime(episodes["last_observed_session"])
    tickers = sorted(episodes["ticker"].unique())
    frames = {
        ticker: pd.read_csv(snapshot / manifest["files"][ticker]["path"], parse_dates=["Date"])
        for ticker in tickers
    }
    rows, failures = [], {}
    for event in episodes.to_dict("records"):
        try:
            result = measure_episode(frames[event["ticker"]], event["last_observed_session"], protocol)
            if result is not None:
                rows.append({
                    "ticker": event["ticker"],
                    "episode_id": event["episode_id"],
                    "signal_date": pd.Timestamp(event["last_observed_session"]).date().isoformat(),
                    "path_label": event["path_label"],
                    **result,
                })
        except Exception as exc:
            failures[str(event["episode_id"])] = f"{type(exc).__name__}: {exc}"
    measured = pd.DataFrame(rows)
    base = summarize_scenario(measured, "base", protocol)
    stress = summarize_scenario(measured, "stress", protocol)
    passed = base["gate_passed"] and stress["gate_passed"]
    report = {
        "report_version": "HERD_CYCLE_VALUE_CEILING_V1",
        "status": "FEASIBILITY_CEILING_PASSED" if passed else "FEASIBILITY_CEILING_FAILED",
        "interpretation": "non-executable upper bound; no action authority",
        "snapshot_id": manifest["snapshot_id"],
        "snapshot_sha256": manifest["snapshot_sha256"],
        "input_episodes": int(len(episodes)),
        "base_costs": base,
        "stress_costs": stress,
        "ready_for_reentry_worthwhile_target_research": bool(passed),
        "limitations": {
            "dividends_excluded_from_both_lanes": True,
            "current_constituents_survivorship_bias": True,
            "oracle_uses_future_prices": True,
        },
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
        "failures": failures,
    }
    return measured, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--episodes", type=Path, required=True)
    parser.add_argument("--events-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()
    events, report = run(args.snapshot, args.episodes)
    args.events_output.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(args.events_output, index=False)
    args.report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
