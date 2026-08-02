"""Run non-predictive fixed-policy economic baselines on locked S1 events."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from herd.fixed_policy_economic_engine import (
    FixedPolicyEconomicError,
    PreparedEconomicPrices,
    evaluate_prepared_fixed_policy,
    prepare_economic_prices,
)
from herd.profit_giveback_cycle_execution import adjusted_execution_prices


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
ROWS_PATH = ROOT / "data/reports/fixed_policy_economic_baselines_v1.csv.gz"
REPORT_PATH = ROOT / "data/reports/fixed_policy_economic_baselines_v1.json"
CONTRACT_VERSION = "HERD_FIXED_POLICY_ECONOMIC_BASELINES_V1"
EXPECTED_POLICIES = {
    "MATCHED_HOLD",
    "TRIM_KEEP_CASH",
    "TRIM_REENTER_21",
    "TRIM_REENTER_63",
    "TRIM_TO_SPY_HORIZON",
}
EXPECTED_FORBIDDEN = {
    "USE_SUCCESS_LABEL_TO_SELECT_OR_EXECUTE_POLICY",
    "SELECT_BEST_BASELINE_AS_ACTION_CANDIDATE",
    "CHANGE_REENTRY_WAIT_AFTER_RESULTS",
    "USE_FUTURE_LOW_OR_OUTCOME_PATH_FOR_EXECUTION",
    "COUNT_KEEP_CASH_AS_COMPLETED_CYCLE",
    "POOL_PRIMARY_AND_INDEPENDENT_FOR_ADMISSION",
    "AUTHORIZE_OPERATIONAL_ACTION",
    "OPEN_BLIND_HOLDOUT",
}


class FixedPolicyBaselinesError(RuntimeError):
    """Raised when the locked baseline population or execution changes."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise FixedPolicyBaselinesError(f"missing baseline input: {relative}")
    return path


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if (
        contract.get("contract_version") != CONTRACT_VERSION
        or contract.get("status") != "LOCKED_BEFORE_BASELINE_RESULTS"
        or contract.get("objective")
        != "ESTABLISH_NON_PREDICTIVE_ECONOMIC_FLOORS_FOR_FIXED_FIVE_PERCENT_POLICIES"
    ):
        raise FixedPolicyBaselinesError("baseline contract is not locked")

    for item in contract.get("inputs", []):
        input_path = _rooted(item["path"])
        if _sha256(input_path) != item.get("sha256"):
            raise FixedPolicyBaselinesError(
                f"pinned baseline input changed: {item['path']}"
            )
    if len(contract.get("inputs", [])) != 5:
        raise FixedPolicyBaselinesError("baseline input set is incomplete")

    population = contract.get("event_population", {})
    allowed = population.get("allowed_input_columns", [])
    if (
        set(allowed)
        != {"ticker", "universe_role", "signal_date", "outcome_end", "fold_id"}
        or len(allowed) != 5
        or population.get("future_label_columns_forbidden_as_policy_inputs")
        is not True
        or population.get("maximum_events_per_ticker_year", 99) > 2
        or population.get("outcome_must_end_inside_fold") is not True
    ):
        raise FixedPolicyBaselinesError("event population boundary changed")

    execution = contract.get("execution", {})
    if (
        execution.get("starting_ticker_shares") != 1.0
        or execution.get("starting_cash") != 0.0
        or execution.get("trim_fraction") != 0.05
        or execution.get("observation_session")
        != "LAST_AVAILABLE_SESSION_ON_OR_BEFORE_SIGNAL_DATE"
        or execution.get("sale") != "NEXT_SESSION_ADJUSTED_OPEN"
        or execution.get("terminal_session")
        != "LOCKED_OUTCOME_END_126_SESSIONS"
        or execution.get("base_one_way_cost_bps") != 10
        or execution.get("stress_one_way_cost_bps") != [25, 50]
        or execution.get("full_exit_forbidden") is not True
        or execution.get("leverage_forbidden") is not True
    ):
        raise FixedPolicyBaselinesError("execution contract changed")

    policies = {item.get("id"): item for item in contract.get("policies", [])}
    if (
        set(policies) != EXPECTED_POLICIES
        or len(policies) != len(EXPECTED_POLICIES)
    ):
        raise FixedPolicyBaselinesError("fixed baseline set changed")
    if (
        policies["TRIM_REENTER_21"].get("reentry_sessions_after_sale") != 21
        or policies["TRIM_REENTER_63"].get("reentry_sessions_after_sale") != 63
        or policies["TRIM_KEEP_CASH"].get("completed_cycle") is not False
        or policies["TRIM_TO_SPY_HORIZON"].get("destination") != "SPY"
    ):
        raise FixedPolicyBaselinesError("fixed baseline rule changed")

    reporting = contract.get("reporting", {})
    if (
        reporting.get("baseline_selection") != "NONE"
        or reporting.get("candidate_must_be_compared_against_all_baselines")
        is not True
        or reporting.get("report_universes_separately") is not True
        or reporting.get("report_folds_separately") is not True
    ):
        raise FixedPolicyBaselinesError("baseline reporting boundary changed")
    if set(contract.get("forbidden", [])) != EXPECTED_FORBIDDEN:
        raise FixedPolicyBaselinesError("baseline forbidden set changed")

    firewall = contract.get("firewall", {})
    if (
        firewall.get("baseline_results_are_direction_evidence") is not False
        or firewall.get("baseline_results_authorize_action") is not False
        or firewall.get("operational_action") != "HOLD"
        or firewall.get("operational_action_ratio") != 0.0
        or firewall.get("survivorship_safe") is not False
        or firewall.get("blind_holdout_access") is not False
    ):
        raise FixedPolicyBaselinesError("baseline firewall weakened")
    return contract


def _load_manifest(specification: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    path = _rooted(specification["path"])
    return path, json.loads(path.read_text(encoding="utf-8"))


def _load_adjusted_price(
    manifest_path: Path,
    manifest: dict[str, Any],
    ticker: str,
) -> pd.DataFrame:
    item = manifest.get("files", {}).get(ticker)
    if item is None:
        raise FixedPolicyBaselinesError(f"price manifest is missing {ticker}")
    price_path = (manifest_path.parent / item["path"]).resolve()
    if not price_path.is_relative_to(manifest_path.parent.resolve()):
        raise FixedPolicyBaselinesError("price path escaped snapshot")
    if not price_path.is_file() or _sha256(price_path) != item.get("sha256"):
        raise FixedPolicyBaselinesError(f"price receipt changed: {ticker}")
    opener = gzip.open if price_path.suffix == ".gz" else open
    with opener(price_path, "rt", encoding="utf-8") as stream:
        raw = pd.read_csv(stream, parse_dates=["Date"])
    return adjusted_execution_prices(raw)


def _load_inputs(
    contract: dict[str, Any],
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    dict[str, tuple[Path, dict[str, Any]]],
]:
    inputs = contract["inputs"]
    event_spec = next(
        item
        for item in inputs
        if item["path"].endswith(".csv")
        and "profit_take" in item["path"]
    )
    fold_spec = next(item for item in inputs if "walk_forward" in item["path"])
    allowed = contract["event_population"]["allowed_input_columns"]
    raw_events = pd.read_csv(
        _rooted(event_spec["path"]),
        parse_dates=["signal_date", "outcome_end"],
    )
    missing = set(allowed) - set(raw_events.columns)
    if missing:
        raise FixedPolicyBaselinesError(
            f"event ledger is missing columns: {sorted(missing)}"
        )
    events = raw_events[allowed].copy()
    if events.duplicated(["ticker", "signal_date", "fold_id"]).any():
        raise FixedPolicyBaselinesError("event ledger contains duplicate events")
    events["ticker"] = events["ticker"].astype(str).str.upper()
    events["calendar_year"] = events["signal_date"].dt.year
    if (
        events.groupby(["ticker", "calendar_year"]).size().max()
        > contract["event_population"]["maximum_events_per_ticker_year"]
    ):
        raise FixedPolicyBaselinesError("event action budget was exceeded")

    folds = pd.read_csv(
        _rooted(fold_spec["path"]),
        parse_dates=["test_start", "test_end"],
    )
    manifests = {
        item["universe_role"]: _load_manifest(item)
        for item in inputs
        if "universe_role" in item
    }
    if set(manifests) != {"PRIMARY", "INDEPENDENT_CURRENT_CONSTITUENTS"}:
        raise FixedPolicyBaselinesError("universe manifests are incomplete")
    unknown_roles = set(events["universe_role"].astype(str)) - set(manifests)
    if unknown_roles:
        raise FixedPolicyBaselinesError(
            f"event ledger has unknown universe roles: {sorted(unknown_roles)}"
        )
    return events, folds, manifests


def _validate_event_fold(event: Any, fold_by_id: dict[str, Any]) -> None:
    fold = fold_by_id.get(str(event.fold_id))
    if fold is None:
        raise FixedPolicyBaselinesError(f"unknown event fold: {event.fold_id}")
    if not (
        pd.Timestamp(fold.test_start) <= pd.Timestamp(event.signal_date)
        and pd.Timestamp(event.outcome_end) <= pd.Timestamp(fold.test_end)
    ):
        raise FixedPolicyBaselinesError("event outcome escaped its OOS fold")


def _summary(
    rows: pd.DataFrame,
    dimensions: list[str] | None = None,
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    keys = dimensions or ["universe_role", "policy_id", "one_way_cost_bps"]
    grouped = rows.groupby(keys, sort=True)
    for group_values, subset in grouped:
        values = (
            group_values
            if isinstance(group_values, tuple)
            else (group_values,)
        )
        delta = subset["normalized_net_terminal_wealth_delta"].astype(float)
        missed = subset["missed_upside_cost"].astype(float)
        summaries.append(
            {
                **{
                    key: (int(value) if key == "one_way_cost_bps" else value)
                    for key, value in zip(keys, values, strict=True)
                },
                "events": int(len(subset)),
                "tickers": int(subset["ticker"].nunique()),
                "folds": int(subset["fold_id"].nunique()),
                "positive_net_value_rate": float((delta > 0).mean()),
                "median_normalized_net_terminal_wealth_delta": float(delta.median()),
                "mean_normalized_net_terminal_wealth_delta": float(delta.mean()),
                "median_terminal_share_delta": float(
                    subset["terminal_share_delta"].median()
                ),
                "positive_terminal_share_delta_rate": float(
                    (subset["terminal_share_delta"] > 0).mean()
                ),
                "median_downside_avoided": float(
                    subset["downside_avoided"].median()
                ),
                "median_average_equity_exposure": float(
                    subset["average_equity_exposure"].median()
                ),
                "median_one_way_turnover": float(
                    subset["one_way_turnover"].median()
                ),
                "completed_policy_rate": float(
                    subset["completed_policy"].astype(bool).mean()
                ),
                "missed_upside_cost_p95": float(np.quantile(missed, 0.95)),
            }
        )
    return summaries


def run(
    contract_path: Path = CONTRACT_PATH,
    rows_path: Path = ROWS_PATH,
    report_path: Path = REPORT_PATH,
) -> dict[str, Any]:
    contract = load_contract(contract_path)
    events, folds, manifests = _load_inputs(contract)
    fold_by_id = {
        str(row.fold_id): row for row in folds.itertuples(index=False)
    }
    policies = [item["id"] for item in contract["policies"]]
    costs = [
        int(contract["execution"]["base_one_way_cost_bps"]),
        *[int(value) for value in contract["execution"]["stress_one_way_cost_bps"]],
    ]
    price_cache: dict[tuple[str, str], PreparedEconomicPrices] = {}
    result_rows: list[dict[str, Any]] = []
    exclusions: list[dict[str, str]] = []

    for event in events.sort_values(
        ["universe_role", "fold_id", "ticker", "signal_date"]
    ).itertuples(index=False):
        try:
            _validate_event_fold(event, fold_by_id)
            manifest_path, manifest = manifests[str(event.universe_role)]
            ticker_key = (str(event.universe_role), str(event.ticker))
            spy_key = (str(event.universe_role), "SPY")
            if ticker_key not in price_cache:
                price_cache[ticker_key] = prepare_economic_prices(
                    _load_adjusted_price(manifest_path, manifest, str(event.ticker)),
                    str(event.ticker),
                )
            if spy_key not in price_cache:
                price_cache[spy_key] = prepare_economic_prices(
                    _load_adjusted_price(manifest_path, manifest, "SPY"),
                    "SPY",
                )
            ticker_prices = price_cache[ticker_key]
            spy_prices = price_cache[spy_key]
            for cost in costs:
                for policy_id in policies:
                    result = evaluate_prepared_fixed_policy(
                        ticker_prices=ticker_prices,
                        spy_prices=spy_prices,
                        signal_date=event.signal_date,
                        terminal_date=event.outcome_end,
                        policy_id=policy_id,
                        one_way_cost_bps=cost,
                    ).to_dict()
                    result_rows.append(
                        {
                            "ticker": event.ticker,
                            "universe_role": event.universe_role,
                            "fold_id": event.fold_id,
                            **result,
                        }
                    )
        except (FixedPolicyEconomicError, FixedPolicyBaselinesError) as error:
            exclusions.append(
                {
                    "ticker": str(event.ticker),
                    "universe_role": str(event.universe_role),
                    "fold_id": str(event.fold_id),
                    "signal_date": pd.Timestamp(event.signal_date).date().isoformat(),
                    "reason": str(error),
                }
            )

    rows = pd.DataFrame(result_rows)
    if rows.empty:
        raise FixedPolicyBaselinesError("no fixed policy baseline rows were generated")
    expected_rows = len(events) * len(costs) * len(policies)
    complete = len(rows) == expected_rows and not exclusions
    rows_path.parent.mkdir(parents=True, exist_ok=True)
    rows.to_csv(
        rows_path,
        index=False,
        compression={"method": "gzip", "compresslevel": 6, "mtime": 0},
    )
    report = {
        "report_version": CONTRACT_VERSION,
        "status": (
            "ECONOMIC_BASELINES_COMPLETE_NO_ACTION_AUTHORITY"
            if complete
            else "ECONOMIC_BASELINES_INCOMPLETE"
        ),
        "complete": complete,
        "contract_sha256": _sha256(contract_path),
        "rows_sha256": _sha256(rows_path),
        "input_events": int(len(events)),
        "generated_rows": int(len(rows)),
        "expected_rows": int(expected_rows),
        "excluded_event_count": int(len(exclusions)),
        "excluded_events": exclusions,
        "policies": policies,
        "costs_bps": costs,
        "summaries": _summary(rows),
        "fold_summaries": _summary(
            rows,
            ["universe_role", "fold_id", "policy_id", "one_way_cost_bps"],
        ),
        "baseline_selected": None,
        "direction_evidence_admitted": False,
        "future_label_columns_used": False,
        "same_session_execution": False,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
        "survivorship_safe": False,
        "blind_holdout_access": False,
        "next_stage": "INSTRUMENT_CLASS_LEDGER_V1",
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if not complete:
        raise FixedPolicyBaselinesError(
            "fixed policy baseline population is incomplete; inspect the report"
        )
    return report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
