"""수익 반납 정책 V1의 완결 사이클 경제성을 고정 OOS fold에서 평가한다."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from herd.benchmark_engine import (
    BenchmarkConfig,
    buy_and_hold,
    performance_metrics,
    simulate_fractional_actions,
)
from herd.completed_cycle import match_completed_cycles
from herd.herd_state_s1 import ROOT
from herd.profit_giveback_cycle_execution import (
    adjusted_execution_prices,
    build_action_schedule,
)


CONTRACT_PATH = Path(__file__).with_suffix(".json")
DEFAULT_ROWS = ROOT / "data/reports/profit_giveback_economic_v1_rows.csv"
DEFAULT_ACTIONS = ROOT / "data/reports/profit_giveback_economic_v1_actions.csv"
DEFAULT_REPORT = ROOT / "data/reports/profit_giveback_economic_v1.json"


class ProfitGivebackEconomicV1Error(RuntimeError):
    """경제성 계약, 고정 입력 또는 시점 정합성이 깨졌을 때 발생한다."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ProfitGivebackEconomicV1Error(
            f"missing economic evaluation input: {relative}"
        )
    return path


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if (
        contract.get("contract_version")
        != "HERD_PROFIT_GIVEBACK_ECONOMIC_V1"
        or contract.get("status") != "LOCKED_BEFORE_ECONOMIC_RESULTS"
    ):
        raise ProfitGivebackEconomicV1Error("economic contract is not locked")
    execution = contract["execution_contract"]
    if (
        execution["trim_fraction_of_current_shares"] != 0.05
        or execution["minimum_reentry_delay_calendar_days"] < 56
        or execution["reentry_fraction_of_available_cash"] != 1.0
    ):
        raise ProfitGivebackEconomicV1Error("sparse completed-cycle rule changed")
    decision = contract["decision_policy"]
    if (
        decision["operational_action_ratio_before_promotion"] != 0.0
        or decision["blind_holdout_access"]
        or decision["threshold_retuning_after_results"]
    ):
        raise ProfitGivebackEconomicV1Error("research boundary was weakened")
    if (
        contract["inputs"]["business_report"]["permitted_role"]
        != "SAFETY_VETO_ONLY"
        or contract["business_time_contract"]["pass_is_directional_evidence"]
    ):
        raise ProfitGivebackEconomicV1Error(
            "rejected business evidence cannot become a direction signal"
        )
    for specification in contract["inputs"].values():
        input_path = _rooted(specification["path"])
        if _sha256(input_path) != specification["sha256"]:
            raise ProfitGivebackEconomicV1Error(
                f"pinned input changed: {specification['path']}"
            )
    return contract


def _load_inputs(
    contract: dict[str, Any],
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    dict[str, pd.DataFrame],
    pd.DataFrame,
]:
    policy_report = json.loads(
        _rooted(contract["inputs"]["policy_report"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    if (
        policy_report.get("status")
        != contract["inputs"]["policy_report"]["required_status"]
        or policy_report.get("economic_evaluation_executed")
        or policy_report.get("operational_action_ratio") != 0.0
    ):
        raise ProfitGivebackEconomicV1Error("policy event report is not safe")
    events = pd.read_csv(
        _rooted(contract["inputs"]["policy_events"]["path"]),
        parse_dates=[
            "signal_date",
            "last_observed_session",
            "POSITION_ENTRY_DATE",
        ],
    )

    transition_spec = contract["inputs"]["transition_report"]
    transition_report_path = _rooted(transition_spec["path"])
    transition_report = json.loads(
        transition_report_path.read_text(encoding="utf-8")
    )
    if (
        transition_report.get("status") != transition_spec["required_status"]
        or transition_report.get("future_outcomes_read")
        or transition_report.get("operational_action_ratio") != 0.0
    ):
        raise ProfitGivebackEconomicV1Error("transition report is not safe")
    panel = transition_report["panels"][transition_spec["panel_role"]]
    transition_path = _rooted(panel["path"])
    if _sha256(transition_path) != panel["sha256"]:
        raise ProfitGivebackEconomicV1Error("transition panel hash changed")
    transitions = pd.read_csv(
        transition_path,
        compression="gzip",
        parse_dates=["signal_date", "last_observed_session"],
    )

    business_report = json.loads(
        _rooted(contract["inputs"]["business_report"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    if (
        business_report.get("decision")
        != contract["inputs"]["business_report"]["required_decision"]
        or business_report.get("add_buy_veto_authorized")
        or business_report.get("operational_action_ratio") != 0.0
    ):
        raise ProfitGivebackEconomicV1Error(
            "business evidence role no longer matches the locked veto-only use"
        )
    business = pd.read_csv(
        _rooted(contract["inputs"]["business_features"]["path"])
    )
    business["month_end"] = pd.to_datetime(business["month_end"])
    business["business_available_date"] = (
        business["month_end"] + pd.Timedelta(days=1)
    )
    business["latest_fact_accepted_at"] = pd.to_datetime(
        business["latest_fact_accepted_at"],
        utc=True,
        errors="coerce",
    ).dt.tz_convert(None)

    price_manifest_path = _rooted(
        contract["inputs"]["price_snapshot_manifest"]["path"]
    )
    price_manifest = json.loads(price_manifest_path.read_text(encoding="utf-8"))
    tickers = sorted(set(transitions["ticker"]))
    prices: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        item = price_manifest["files"].get(ticker)
        if item is None:
            raise ProfitGivebackEconomicV1Error(
                f"price manifest is missing {ticker}"
            )
        price_path = price_manifest_path.parent / item["path"]
        if _sha256(price_path) != item["sha256"]:
            raise ProfitGivebackEconomicV1Error(f"price hash changed: {ticker}")
        opener = gzip.open if price_path.suffix == ".gz" else open
        with opener(price_path, "rt", encoding="utf-8") as stream:
            prices[ticker] = pd.read_csv(stream, parse_dates=["Date"])

    fold_spec = contract["inputs"]["fold_manifest"]
    fold_manifest_path = _rooted(fold_spec["path"])
    fold_manifest = json.loads(fold_manifest_path.read_text(encoding="utf-8"))
    lane = fold_manifest["files"][fold_spec["lane"]]
    fold_path = fold_manifest_path.parent / lane["path"]
    if (
        lane["fold_count"] != fold_spec["required_folds"]
        or lane["sha256"] != fold_spec["lane_sha256"]
        or _sha256(fold_path) != lane["sha256"]
    ):
        raise ProfitGivebackEconomicV1Error("OOS fold receipt changed")
    folds = pd.read_csv(
        fold_path,
        parse_dates=["test_start", "test_end"],
    )
    return events, transitions, business, prices, folds


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    return value


def _evaluate_policy(
    *,
    policy_id: str,
    ticker: str,
    fold_id: str,
    prices: pd.DataFrame,
    actions: pd.DataFrame,
    one_way_cost_bps: int,
) -> dict[str, Any]:
    half_cost = one_way_cost_bps / 20_000
    config = BenchmarkConfig(
        initial_cash=10_000.0,
        fee_rate=half_cost,
        slippage_rate=half_cost,
        annual_cash_yield=0.0,
        execution_lag=1,
        initial_weight=1.0,
    )
    benchmark = buy_and_hold(prices, config=config)
    completed = simulate_fractional_actions(
        policy_id,
        prices,
        actions,
        config=config,
    )
    sell_only_actions = actions.copy()
    sell_only_actions.loc[
        sell_only_actions["action"].eq("BUY"), ["action", "ratio"]
    ] = ["HOLD", 0.0]
    keep_cash = simulate_fractional_actions(
        f"{policy_id}_KEEP_CASH",
        prices,
        sell_only_actions,
        config=config,
    )
    metrics = performance_metrics(completed, benchmark)
    keep_cash_metrics = performance_metrics(keep_cash, benchmark)
    audit = match_completed_cycles(completed.trades)
    completed_cycles = audit.completed_cycles
    executed = [trade for trade in completed.trades if trade.signal_date is not None]
    sells = [trade for trade in executed if trade.side == "SELL"]
    buys = [trade for trade in executed if trade.side == "BUY"]
    return {
        "policy_id": policy_id,
        "fold_id": fold_id,
        "ticker": ticker,
        "one_way_cost_bps": one_way_cost_bps,
        "activated": bool(sells),
        "executed_sell_count": len(sells),
        "executed_reentry_count": len(buys),
        "completed_cycle_count": len(completed_cycles),
        "positive_completed_cycle_count": sum(
            cycle.share_delta > 0 for cycle in completed_cycles
        ),
        "completed_cycle_share_delta": sum(
            cycle.share_delta for cycle in completed_cycles
        ),
        "completed_cycle_ticker": bool(completed_cycles),
        "open_sale_count": audit.open_sale_count,
        "open_sale_cash": audit.open_sale_cash,
        "unmatched_buy_cost": audit.unmatched_buy_cost,
        "cagr": metrics["cagr"],
        "excess_cagr": metrics["excess_cagr"],
        "max_drawdown": metrics["max_drawdown"],
        "mdd_improvement": (
            float(metrics["max_drawdown"])
            - float(performance_metrics(benchmark)["max_drawdown"])
        ),
        "sortino": metrics["sortino"],
        "calmar": metrics["calmar"],
        "upside_capture": metrics["upside_capture"],
        "downside_capture": metrics["downside_capture"],
        "average_exposure": metrics["average_exposure"],
        "turnover": metrics["turnover"],
        "terminal_wealth_delta": metrics["terminal_wealth_delta"],
        "terminal_share_delta": metrics["terminal_share_delta"],
        "final_equity": metrics["final_equity"],
        "buy_hold_final_equity": float(benchmark.equity.iloc[-1]),
        "keep_cash_terminal_wealth_delta": keep_cash_metrics[
            "terminal_wealth_delta"
        ],
        "keep_cash_final_equity": keep_cash_metrics["final_equity"],
    }


def _median(rows: pd.DataFrame, column: str) -> float | None:
    values = pd.to_numeric(rows[column], errors="coerce").dropna()
    return float(values.median()) if len(values) else None


def summarize_policy(
    rows: pd.DataFrame,
    policy_id: str,
    one_way_cost_bps: int,
) -> dict[str, Any]:
    subset = rows[
        rows["policy_id"].eq(policy_id)
        & rows["one_way_cost_bps"].eq(one_way_cost_bps)
    ]
    activated = subset[subset["activated"].astype(bool)]
    completed = subset[subset["completed_cycle_count"].gt(0)]
    total_cycles = int(subset["completed_cycle_count"].sum())
    positive_cycles = int(subset["positive_completed_cycle_count"].sum())
    return {
        "cohorts": int(len(subset)),
        "activated_cohorts": int(len(activated)),
        "completed_cycles": total_cycles,
        "completed_cycle_tickers": int(completed["ticker"].nunique()),
        "completed_cycle_folds": int(completed["fold_id"].nunique()),
        "positive_completed_cycle_rate": (
            positive_cycles / total_cycles if total_cycles else None
        ),
        "positive_terminal_wealth_rate_activated": (
            float(activated["terminal_wealth_delta"].gt(0).mean())
            if len(activated)
            else None
        ),
        "median_excess_cagr_activated": _median(activated, "excess_cagr"),
        "median_mdd_improvement_activated": _median(
            activated, "mdd_improvement"
        ),
        "median_upside_capture_activated": _median(
            activated, "upside_capture"
        ),
        "median_downside_capture_activated": _median(
            activated, "downside_capture"
        ),
        "median_average_exposure_activated": _median(
            activated, "average_exposure"
        ),
        "median_terminal_wealth_delta_activated": _median(
            activated, "terminal_wealth_delta"
        ),
        "median_keep_cash_terminal_wealth_delta_activated": _median(
            activated, "keep_cash_terminal_wealth_delta"
        ),
        "median_terminal_share_delta_completed": _median(
            completed, "terminal_share_delta"
        ),
    }


def _decision(
    rows: pd.DataFrame,
    folds: pd.DataFrame,
    contract: dict[str, Any],
) -> dict[str, Any]:
    gate = contract["adoption_gates"]
    base_cost = int(contract["execution_contract"]["base_one_way_cost_bps"])
    service = summarize_policy(rows, "HERD_GIVEBACK_S1", base_cost)
    generic = summarize_policy(rows, "GIVEBACK_BASELINE", base_cost)
    stress_25 = summarize_policy(rows, "HERD_GIVEBACK_S1", 25)

    paired = rows[
        rows["one_way_cost_bps"].eq(base_cost)
    ].pivot_table(
        index=["fold_id", "ticker"],
        columns="policy_id",
        values="final_equity",
        aggfunc="first",
    )
    paired = paired.dropna(
        subset=["GIVEBACK_BASELINE", "HERD_GIVEBACK_S1"]
    )
    service_activated_keys = rows[
        rows["policy_id"].eq("HERD_GIVEBACK_S1")
        & rows["one_way_cost_bps"].eq(base_cost)
        & rows["activated"].astype(bool)
    ][["fold_id", "ticker"]]
    keys = pd.MultiIndex.from_frame(service_activated_keys)
    paired = paired.loc[paired.index.intersection(keys)]
    incremental = (
        float(
            (
                paired["HERD_GIVEBACK_S1"]
                - paired["GIVEBACK_BASELINE"]
            ).median()
        )
        if len(paired)
        else None
    )

    checks = {
        "minimum_fold_count": len(folds) >= gate["minimum_fold_count"],
        "minimum_completed_cycles": service["completed_cycles"]
        >= gate["minimum_completed_cycles"],
        "minimum_completed_cycle_tickers": service[
            "completed_cycle_tickers"
        ]
        >= gate["minimum_completed_cycle_tickers"],
        "minimum_completed_cycle_folds": service["completed_cycle_folds"]
        >= gate["minimum_completed_cycle_folds"],
        "minimum_positive_completed_cycle_rate": (
            service["positive_completed_cycle_rate"] is not None
            and service["positive_completed_cycle_rate"]
            >= gate["minimum_positive_completed_cycle_rate"]
        ),
        "minimum_positive_terminal_wealth_rate_activated": (
            service["positive_terminal_wealth_rate_activated"] is not None
            and service["positive_terminal_wealth_rate_activated"]
            >= gate["minimum_positive_terminal_wealth_rate_activated"]
        ),
        "minimum_median_excess_cagr_activated": (
            service["median_excess_cagr_activated"] is not None
            and service["median_excess_cagr_activated"]
            > gate["minimum_median_excess_cagr_activated"]
        ),
        "minimum_median_mdd_improvement_activated": (
            service["median_mdd_improvement_activated"] is not None
            and service["median_mdd_improvement_activated"]
            >= gate["minimum_median_mdd_improvement_activated"]
        ),
        "minimum_median_upside_capture_activated": (
            service["median_upside_capture_activated"] is not None
            and service["median_upside_capture_activated"]
            >= gate["minimum_median_upside_capture_activated"]
        ),
        "minimum_median_average_exposure_activated": (
            service["median_average_exposure_activated"] is not None
            and service["median_average_exposure_activated"]
            >= gate["minimum_median_average_exposure_activated"]
        ),
        "minimum_stress_25bps_median_terminal_wealth_delta": (
            stress_25["median_terminal_wealth_delta_activated"] is not None
            and stress_25["median_terminal_wealth_delta_activated"]
            > gate["minimum_stress_25bps_median_terminal_wealth_delta"]
        ),
        "minimum_incremental_median_terminal_wealth_vs_generic_baseline": (
            incremental is not None
            and incremental
            > gate[
                "minimum_incremental_median_terminal_wealth_vs_generic_baseline"
            ]
        ),
    }
    passed = all(checks.values())
    return {
        "status": (
            "PERSONAL_POLICY_PREHOLDOUT_PASSED"
            if passed
            else "PERSONAL_POLICY_REJECTED_PREHOLDOUT"
        ),
        "passed": passed,
        "checks": checks,
        "service_base": service,
        "generic_base": generic,
        "service_stress_25bps": stress_25,
        "service_stress_50bps": summarize_policy(
            rows, "HERD_GIVEBACK_S1", 50
        ),
        "incremental_median_terminal_wealth_vs_generic_baseline": incremental,
    }


def _action_summary(actions: pd.DataFrame) -> dict[str, Any]:
    if actions.empty:
        return {"policies": {}}
    policies = {}
    for policy_id, rows in actions.groupby("policy_id", sort=True):
        blocked = rows[rows["action"].eq("REENTRY_BLOCKED")]
        policies[policy_id] = {
            "trim_signals": int(rows["action"].eq("SELL").sum()),
            "reentry_signals": int(rows["action"].eq("BUY").sum()),
            "blocked_reentry_candidates": int(len(blocked)),
            "blocked_by_state": {
                str(state): int(count)
                for state, count in blocked["business_gate"]
                .value_counts()
                .sort_index()
                .items()
            },
        }
    return {"policies": policies}


def run(
    contract_path: Path = CONTRACT_PATH,
    rows_path: Path = DEFAULT_ROWS,
    actions_path: Path = DEFAULT_ACTIONS,
    report_path: Path = DEFAULT_REPORT,
) -> dict[str, Any]:
    contract = load_contract(contract_path)
    events, transitions, business, raw_prices, folds = _load_inputs(contract)
    tickers = sorted(set(transitions["ticker"]))
    policies = [item["id"] for item in json.loads(
        _rooted(contract["inputs"]["policy_contract"]["path"]).read_text(
            encoding="utf-8"
        )
    )["policies"]]
    costs = [
        int(contract["execution_contract"]["base_one_way_cost_bps"]),
        *[
            int(value)
            for value in contract["execution_contract"][
                "stress_one_way_cost_bps"
            ]
        ],
    ]
    result_rows: list[dict[str, Any]] = []
    action_rows: list[dict[str, Any]] = []
    for fold in folds.itertuples(index=False):
        for ticker in tickers:
            prices = adjusted_execution_prices(raw_prices[ticker]).loc[
                pd.Timestamp(fold.test_start) : pd.Timestamp(fold.test_end)
            ]
            if len(prices) < 200:
                continue
            ticker_transitions = transitions[
                transitions["ticker"].eq(ticker)
                & transitions["last_observed_session"].between(
                    pd.Timestamp(fold.test_start),
                    pd.Timestamp(fold.test_end),
                )
            ]
            for policy_id in policies:
                actions, audit = build_action_schedule(
                    policy_id=policy_id,
                    ticker=ticker,
                    fold_id=fold.fold_id,
                    prices=prices,
                    events=events,
                    transitions=ticker_transitions,
                    business=business,
                    minimum_reentry_days=int(
                        contract["execution_contract"][
                            "minimum_reentry_delay_calendar_days"
                        ]
                    ),
                )
                action_rows.extend(audit)
                for cost in costs:
                    result_rows.append(
                        _evaluate_policy(
                            policy_id=policy_id,
                            ticker=ticker,
                            fold_id=fold.fold_id,
                            prices=prices,
                            actions=actions,
                            one_way_cost_bps=cost,
                        )
                    )
    rows = pd.DataFrame(result_rows)
    actions = pd.DataFrame(action_rows)
    rows_path.parent.mkdir(parents=True, exist_ok=True)
    rows.to_csv(rows_path, index=False)
    actions.to_csv(actions_path, index=False)
    decision = _decision(rows, folds, contract)
    report = {
        "report_version": "HERD_PROFIT_GIVEBACK_ECONOMIC_V1",
        **decision,
        "contract_sha256": _sha256(contract_path),
        "rows_sha256": _sha256(rows_path),
        "actions_sha256": _sha256(actions_path),
        "rows": int(len(rows)),
        "action_audit_rows": int(len(actions)),
        "folds": int(len(folds)),
        "tickers": int(rows["ticker"].nunique()),
        "costs_bps": costs,
        "action_audit": _action_summary(actions),
        "failed_gates": [
            key for key, passed in decision["checks"].items() if not passed
        ],
        "price_adjustment": contract["price_contract"],
        "business_gate_role": "SAFETY_VETO_ONLY",
        "business_directional_evidence_used": False,
        "external_contributions": False,
        "future_prices_used_for_signal": False,
        "same_session_execution": False,
        "thresholds_changed_after_results": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
        "survivorship_safe": False,
    }
    report_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            default=_json_value,
        )
        + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--actions", type=Path, default=DEFAULT_ACTIONS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.contract, args.rows, args.actions, args.report),
            ensure_ascii=False,
            indent=2,
            default=_json_value,
        )
    )


if __name__ == "__main__":
    main()
