"""사전등록한 수익 반납 정책의 OOS 코호트별 관측 가능 trim 후보를 생성한다."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from herd.herd_state_s1 import ROOT


CONTRACT_PATH = Path(__file__).with_suffix(".json")
DEFAULT_EVENTS = ROOT / "data/reports/profit_giveback_policy_v1_events.csv"
DEFAULT_REPORT = ROOT / "data/reports/profit_giveback_policy_v1.json"


class ProfitGivebackPolicyV1Error(RuntimeError):
    """정책 계약·고정 입력·시간 순서가 깨졌을 때 발생한다."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ProfitGivebackPolicyV1Error(f"missing policy input: {relative}")
    return path


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if (
        contract.get("contract_version") != "HERD_PROFIT_GIVEBACK_POLICY_V1"
        or contract.get("status") != "LOCKED_BEFORE_POLICY_EVENT_RESULTS"
    ):
        raise ProfitGivebackPolicyV1Error("profit giveback contract is not locked")
    if contract["position_contract"]["future_price_allowed"]:
        raise ProfitGivebackPolicyV1Error("policy cannot use a future price")
    execution = contract["execution_policy"]
    if (
        execution["trim_fraction_of_current_shares"] != 0.05
        or execution["maximum_cumulative_trim_fraction"] > 0.15
        or execution["maximum_trim_events_per_ticker_year"] > 2
    ):
        raise ProfitGivebackPolicyV1Error("sparse five-percent policy was weakened")
    if contract["claim_boundary"]["operational_action_ratio"] != 0.0:
        raise ProfitGivebackPolicyV1Error("research event cannot authorize an action")
    if [item["id"] for item in contract["policies"]] != [
        "GIVEBACK_BASELINE",
        "HERD_GIVEBACK_S1",
    ]:
        raise ProfitGivebackPolicyV1Error("policy candidate set changed")
    for specification in contract["inputs"].values():
        path_value = specification["path"]
        path = _rooted(path_value)
        if _sha256(path) != specification["sha256"]:
            raise ProfitGivebackPolicyV1Error(f"pinned input changed: {path_value}")
    return contract


def _load_inputs(
    contract: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], pd.DataFrame]:
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
        raise ProfitGivebackPolicyV1Error("unsafe transition report")
    primary = transition_report["panels"]["PRIMARY"]
    transition_path = _rooted(primary["path"])
    if _sha256(transition_path) != primary["sha256"]:
        raise ProfitGivebackPolicyV1Error("primary transition panel hash changed")
    transitions = pd.read_csv(
        transition_path,
        compression="gzip",
        parse_dates=["signal_date", "last_observed_session"],
    )

    price_manifest_path = _rooted(
        contract["inputs"]["price_snapshot_manifest"]["path"]
    )
    price_manifest = json.loads(price_manifest_path.read_text(encoding="utf-8"))
    tickers = sorted(set(transitions["ticker"]))
    prices = {}
    for ticker in tickers:
        item = price_manifest["files"][ticker]
        path = price_manifest_path.parent / item["path"]
        if _sha256(path) != item["sha256"]:
            raise ProfitGivebackPolicyV1Error(f"price hash changed: {ticker}")
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            prices[ticker] = pd.read_csv(stream, parse_dates=["Date"]).sort_values(
                "Date"
            )

    fold_spec = contract["inputs"]["fold_manifest"]
    fold_manifest_path = _rooted(fold_spec["path"])
    fold_manifest = json.loads(fold_manifest_path.read_text(encoding="utf-8"))
    lane = fold_manifest["files"][fold_spec["lane"]]
    if (
        lane["fold_count"] != fold_spec["required_folds"]
        or lane["sha256"] != _sha256(fold_manifest_path.parent / lane["path"])
    ):
        raise ProfitGivebackPolicyV1Error("price timing fold receipt changed")
    folds = pd.read_csv(
        fold_manifest_path.parent / lane["path"],
        parse_dates=["test_start", "test_end"],
    )
    return transitions, prices, folds


def _position_observations(
    rows: pd.DataFrame,
    prices: pd.DataFrame,
    test_start: pd.Timestamp,
    test_end: pd.Timestamp,
) -> pd.DataFrame:
    price = prices.set_index("Date")["Adj Close"].astype(float).sort_index()
    entry_candidates = price.loc[price.index >= test_start]
    if entry_candidates.empty:
        return pd.DataFrame()
    entry_date = entry_candidates.index[0]
    if entry_date > test_end:
        return pd.DataFrame()
    entry_price = float(entry_candidates.iloc[0])
    observations = rows[
        (rows["last_observed_session"] >= entry_date)
        & (rows["last_observed_session"] <= test_end)
    ].copy()
    if observations.empty:
        return observations
    observed_prices = price.reindex(
        pd.DatetimeIndex(observations["last_observed_session"])
    )
    if observed_prices.isna().any():
        raise ProfitGivebackPolicyV1Error("weekly state lacks an exact observed price")
    observations["POSITION_ENTRY_DATE"] = entry_date
    observations["POSITION_ENTRY_PRICE"] = entry_price
    observations["POSITION_PRICE"] = observed_prices.to_numpy()
    observations["POSITION_PEAK_PRICE"] = observations["POSITION_PRICE"].cummax()
    observations["PEAK_GAIN"] = (
        observations["POSITION_PEAK_PRICE"] / entry_price - 1
    )
    observations["DRAWDOWN_FROM_PEAK"] = (
        observations["POSITION_PRICE"] / observations["POSITION_PEAK_PRICE"] - 1
    )
    denominator = observations["POSITION_PEAK_PRICE"] - entry_price
    observations["PROFIT_GIVEBACK_FRACTION"] = (
        (observations["POSITION_PEAK_PRICE"] - observations["POSITION_PRICE"])
        / denominator.where(denominator > 0)
    ).fillna(0.0)
    observations["RECENT_RUSH_13W"] = (
        observations["HERD_STAGE"].eq("RUSH").rolling(13, min_periods=1).max().astype(bool)
    )
    return observations


def _policy_mask(rows: pd.DataFrame, policy: dict[str, Any]) -> pd.Series:
    mask = (
        (rows["PEAK_GAIN"] >= float(policy["minimum_peak_gain"]))
        & (
            rows["DRAWDOWN_FROM_PEAK"]
            <= -float(policy["minimum_peak_drawdown"])
        )
        & (
            rows["PROFIT_GIVEBACK_FRACTION"]
            >= float(policy["minimum_profit_giveback_fraction"])
        )
    )
    if policy["requires_recent_rush"]:
        mask &= rows["RECENT_RUSH_13W"]
    required = policy["required_transitions"]
    if required:
        mask &= rows["HERD_TRANSITION"].isin(required)
    return mask


def _sparsify(
    candidates: pd.DataFrame,
    maximum_per_year: int,
    cooldown_weeks: int,
) -> pd.DataFrame:
    selected = []
    last_date: pd.Timestamp | None = None
    per_year: dict[int, int] = {}
    for row in candidates.sort_values("signal_date").itertuples(index=False):
        date = pd.Timestamp(row.signal_date)
        if per_year.get(date.year, 0) >= maximum_per_year:
            continue
        if last_date is not None and (date - last_date).days < cooldown_weeks * 7:
            continue
        selected.append(row)
        last_date = date
        per_year[date.year] = per_year.get(date.year, 0) + 1
    if not selected:
        return candidates.iloc[0:0].copy()
    return pd.DataFrame(selected, columns=candidates.columns)


def build_policy_events(
    transitions: pd.DataFrame,
    prices: dict[str, pd.DataFrame],
    folds: pd.DataFrame,
    contract: dict[str, Any],
) -> pd.DataFrame:
    execution = contract["execution_policy"]
    event_parts = []
    for fold in folds.itertuples(index=False):
        for ticker, ticker_rows in transitions.groupby("ticker", sort=False):
            observations = _position_observations(
                ticker_rows,
                prices[ticker],
                pd.Timestamp(fold.test_start),
                pd.Timestamp(fold.test_end),
            )
            if observations.empty:
                continue
            for policy in contract["policies"]:
                candidates = observations[_policy_mask(observations, policy)].copy()
                selected = _sparsify(
                    candidates,
                    int(execution["maximum_trim_events_per_ticker_year"]),
                    int(execution["minimum_trim_cooldown_weeks"]),
                )
                if selected.empty:
                    continue
                selected["fold_id"] = fold.fold_id
                selected["policy_id"] = policy["id"]
                selected["policy_role"] = policy["role"]
                selected["research_action"] = "TRIM_REVIEW_5_PERCENT"
                selected["trim_fraction"] = float(
                    execution["trim_fraction_of_current_shares"]
                )
                event_parts.append(selected)
    if not event_parts:
        return pd.DataFrame()
    events = pd.concat(event_parts, ignore_index=True)
    events = events.sort_values(["policy_id", "fold_id", "ticker", "signal_date"])
    events.insert(
        0,
        "event_id",
        [
            f"{row.policy_id}-{row.fold_id}-{row.ticker}-{pd.Timestamp(row.signal_date).date()}"
            for row in events.itertuples(index=False)
        ],
    )
    keep = [
        "event_id",
        "policy_id",
        "policy_role",
        "fold_id",
        "ticker",
        "signal_date",
        "last_observed_session",
        "POSITION_ENTRY_DATE",
        "POSITION_ENTRY_PRICE",
        "POSITION_PRICE",
        "POSITION_PEAK_PRICE",
        "PEAK_GAIN",
        "DRAWDOWN_FROM_PEAK",
        "PROFIT_GIVEBACK_FRACTION",
        "RECENT_RUSH_13W",
        "HERD_STATE",
        "HERD_STAGE",
        "HERD_TRANSITION",
        "research_action",
        "trim_fraction",
    ]
    return events[keep].reset_index(drop=True)


def _event_summary(
    events: pd.DataFrame,
    folds: pd.DataFrame,
    contract: dict[str, Any],
) -> dict[str, Any]:
    gates = contract["event_generation_gates"]
    by_policy = {}
    for policy in contract["policies"]:
        rows = events[events["policy_id"] == policy["id"]]
        by_policy[policy["id"]] = {
            "events": int(len(rows)),
            "tickers": int(rows["ticker"].nunique()),
            "folds": int(rows["fold_id"].nunique()),
            "median_peak_gain": (
                float(rows["PEAK_GAIN"].median()) if len(rows) else None
            ),
            "median_drawdown_from_peak": (
                float(rows["DRAWDOWN_FROM_PEAK"].median()) if len(rows) else None
            ),
            "median_profit_giveback_fraction": (
                float(rows["PROFIT_GIVEBACK_FRACTION"].median())
                if len(rows)
                else None
            ),
        }
    baseline = by_policy["GIVEBACK_BASELINE"]
    service = by_policy["HERD_GIVEBACK_S1"]
    if events.empty:
        maximum_per_ticker_year = 0
    else:
        counted = events.assign(
            year=pd.to_datetime(events["signal_date"]).dt.year
        ).groupby(["policy_id", "fold_id", "ticker", "year"]).size()
        maximum_per_ticker_year = int(counted.max())
    checks = {
        "required_fold_count": len(folds) == gates["required_fold_count"],
        "minimum_giveback_baseline_events": baseline["events"]
        >= gates["minimum_giveback_baseline_events"],
        "minimum_service_candidate_events": service["events"]
        >= gates["minimum_service_candidate_events"],
        "minimum_service_candidate_tickers": service["tickers"]
        >= gates["minimum_service_candidate_tickers"],
        "minimum_service_candidate_folds": service["folds"]
        >= gates["minimum_service_candidate_folds"],
        "maximum_events_per_ticker_year": maximum_per_ticker_year
        <= contract["execution_policy"]["maximum_trim_events_per_ticker_year"],
    }
    return {
        "folds": int(len(folds)),
        "policy_results": by_policy,
        "maximum_events_per_ticker_year": maximum_per_ticker_year,
        "checks": checks,
        "passed": all(checks.values()),
    }


def run(
    contract_path: Path = CONTRACT_PATH,
    events_path: Path = DEFAULT_EVENTS,
    report_path: Path = DEFAULT_REPORT,
) -> dict[str, Any]:
    contract = load_contract(contract_path)
    transitions, prices, folds = _load_inputs(contract)
    events = build_policy_events(transitions, prices, folds, contract)
    events_path.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(events_path, index=False)
    summary = _event_summary(events, folds, contract)
    report = {
        "report_version": "HERD_PROFIT_GIVEBACK_POLICY_V1",
        "status": (
            "POLICY_EVENTS_READY"
            if summary["passed"]
            else "POLICY_EVENT_COVERAGE_FAILED"
        ),
        "contract_sha256": _sha256(contract_path),
        "events_sha256": _sha256(events_path),
        "events": int(len(events)),
        **summary,
        "future_prices_used_for_event": False,
        "future_outcomes_labeled": False,
        "economic_evaluation_executed": False,
        "event_is_trade_authority": False,
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
        "survivorship_safe": False,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.contract, args.events, args.report),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
