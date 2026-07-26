"""State S1 Rush 진입에서 5% 익절·재진입 경제 기회의 상한을 측정한다."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
STATE_REPORT_PATH = ROOT / "data/reports/herd_state_s1.json"
OUTPUT_PATH = ROOT / "data/reports/profit_take_opportunity_ceiling_v1.csv"
REPORT_PATH = ROOT / "data/reports/profit_take_opportunity_ceiling_v1.json"
VERSION = "HERD_PROFIT_TAKE_OPPORTUNITY_CEILING_V1"


class OpportunityCeilingError(ValueError):
    """계약·가격·시점 정합성이 깨진 경우."""


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_contract(contract: dict[str, Any]) -> dict[str, Any]:
    if (
        contract.get("contract_version") != VERSION
        or contract.get("status") != "LOCKED_BEFORE_S1_CEILING_RESULTS"
    ):
        raise OpportunityCeilingError("opportunity ceiling is not locked")
    for item in contract["inputs"]:
        path = (ROOT / item["path"]).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise OpportunityCeilingError(f"missing input: {item['path']}")
        if _hash(path) != item["sha256"]:
            raise OpportunityCeilingError(f"input changed: {item['path']}")
    event = contract["event"]
    execution = contract["execution"]
    ceiling = contract["ceilings"]["constrained_oracle"]
    boundary = contract["decision_boundary"]
    if (
        event["model"] != "HERD_STATE_S1"
        or event["maximum_events_per_ticker_calendar_year"] != 2
        or execution["trim_fraction"] != 0.05
        or execution["horizon_sessions"] != 126
        or ceiling["minimum_net_sleeve_share_delta_rate"] != 0.03
        or ceiling["minimum_consecutive_qualifying_sessions"] != 3
        or ceiling["maximum_advance_before_reentry"] != 0.10
        or boundary["pass_does_not_admit_direction_evidence"] is not True
        or boundary["survivorship_safe"] is not False
        or boundary["blind_holdout_access"] is not False
        or boundary["operational_action_ratio"] != 0.0
    ):
        raise OpportunityCeilingError("research boundary changed")
    return contract


def _load_rush_entries() -> pd.DataFrame:
    report = json.loads(STATE_REPORT_PATH.read_text())
    parts = []
    for panel in report["panels"].values():
        path = ROOT / panel["path"]
        if _hash(path) != panel["sha256"]:
            raise OpportunityCeilingError("State S1 panel changed")
        parts.append(pd.read_csv(path, compression="gzip", parse_dates=["signal_date"]))
    state = pd.concat(parts, ignore_index=True).sort_values(["ticker", "signal_date"])
    previous = state.groupby("ticker", sort=False)["HERD_STAGE"].shift()
    entries = state[
        state["HERD_STAGE"].eq("RUSH")
        & previous.notna()
        & previous.ne("RUSH")
    ].copy()
    entries["calendar_year"] = entries["signal_date"].dt.year
    entries["ticker_year_ordinal"] = (
        entries.groupby(["ticker", "calendar_year"], sort=False).cumcount() + 1
    )
    entries["sparse_eligible"] = entries["ticker_year_ordinal"].le(2)
    if entries.duplicated(["ticker", "signal_date"]).any():
        raise OpportunityCeilingError("duplicate S1 Rush entry")
    return entries


def _price_sources() -> dict[str, tuple[Path, str]]:
    sources: dict[str, tuple[Path, str]] = {}
    for relative in (
        "data/snapshots/yf-long14-actions-sector-20260721/manifest.json",
        "data/snapshots/yf-independent-current-sp500-20260721/manifest.json",
    ):
        manifest_path = ROOT / relative
        manifest = json.loads(manifest_path.read_text())
        for ticker, item in manifest["files"].items():
            sources.setdefault(
                ticker, (manifest_path.parent / item["path"], item["sha256"])
            )
    return sources


def _adjusted_prices(path: Path, expected: str) -> pd.DataFrame:
    if _hash(path) != expected:
        raise OpportunityCeilingError(f"price file changed: {path.name}")
    frame = pd.read_csv(path, compression="gzip", parse_dates=["Date"])
    required = {"Date", "Open", "Close", "Adj Close"}
    if not required.issubset(frame.columns):
        raise OpportunityCeilingError(f"missing price columns: {path.name}")
    frame = frame.sort_values("Date").drop_duplicates("Date", keep="last")
    frame["AdjustedOpen"] = (
        frame["Open"].astype(float)
        * frame["Adj Close"].astype(float)
        / frame["Close"].astype(float)
    )
    frame["AdjustedClose"] = frame["Adj Close"].astype(float)
    frame = frame[["Date", "AdjustedOpen", "AdjustedClose"]].dropna()
    if (
        frame.empty
        or not np.isfinite(frame[["AdjustedOpen", "AdjustedClose"]]).all().all()
        or (frame[["AdjustedOpen", "AdjustedClose"]] <= 0).any().any()
    ):
        raise OpportunityCeilingError(f"invalid adjusted prices: {path.name}")
    return frame.reset_index(drop=True)


def _scenario(
    future_opens: np.ndarray,
    sale_open: float,
    *,
    fee: float,
    slippage: float,
    minimum_delta: float,
    minimum_run: int,
    maximum_advance: float,
) -> dict[str, Any]:
    net_sale_cash = sale_open * (1.0 - slippage) * (1.0 - fee)
    reentry_cost = future_opens * (1.0 + slippage) * (1.0 + fee)
    share_delta = net_sale_cash / reentry_cost - 1.0
    absolute_index = int(np.argmax(share_delta))
    absolute_delta = float(share_delta[absolute_index])

    qualifies = share_delta >= minimum_delta
    starts: list[int] = []
    for index in range(len(qualifies) - minimum_run + 1):
        if not qualifies[index : index + minimum_run].all():
            continue
        prior_advance = float((future_opens[: index + 1] / sale_open - 1.0).max())
        if prior_advance <= maximum_advance:
            starts.append(index)
    constrained_index = (
        max(starts, key=lambda index: share_delta[index]) if starts else None
    )
    constrained_delta = (
        float(share_delta[constrained_index]) if constrained_index is not None else 0.0
    )
    return {
        "absolute_available": absolute_delta > 0,
        "absolute_share_delta_rate": max(absolute_delta, 0.0),
        "absolute_time_to_reentry_sessions": absolute_index + 1,
        "constrained_available": constrained_index is not None,
        "constrained_share_delta_rate": constrained_delta,
        "constrained_time_to_reentry_sessions": (
            constrained_index + 1 if constrained_index is not None else None
        ),
        "days_at_or_above_minimum_delta": int(qualifies.sum()),
    }


def measure_entry(
    prices: pd.DataFrame, signal_date: pd.Timestamp, contract: dict[str, Any]
) -> dict[str, Any] | None:
    position = int(prices["Date"].searchsorted(signal_date, side="right"))
    horizon = int(contract["execution"]["horizon_sessions"])
    end = position + horizon
    if position >= len(prices) or end >= len(prices):
        return None
    sale_open = float(prices.iloc[position]["AdjustedOpen"])
    future = prices.iloc[position + 1 : end + 1]
    if len(future) != horizon:
        return None
    ceiling = contract["ceilings"]["constrained_oracle"]
    execution = contract["execution"]
    common = {
        "future_opens": future["AdjustedOpen"].to_numpy(dtype=float),
        "sale_open": sale_open,
        "minimum_delta": ceiling["minimum_net_sleeve_share_delta_rate"],
        "minimum_run": ceiling["minimum_consecutive_qualifying_sessions"],
        "maximum_advance": ceiling["maximum_advance_before_reentry"],
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
    return {
        "sale_date": prices.iloc[position]["Date"].date().isoformat(),
        "outcome_end": prices.iloc[end]["Date"].date().isoformat(),
        "sale_adjusted_open": sale_open,
        **{f"base_{key}": value for key, value in base.items()},
        **{f"stress_{key}": value for key, value in stress.items()},
    }


def _summary(frame: pd.DataFrame, prefix: str) -> dict[str, Any]:
    available = frame[f"{prefix}_constrained_available"].astype(bool)
    conditional = frame.loc[
        available, f"{prefix}_constrained_share_delta_rate"
    ].astype(float)
    return {
        "events": len(frame),
        "tickers": int(frame["ticker"].nunique()),
        "constrained_opportunities": int(available.sum()),
        "absolute_opportunity_rate": float(
            frame[f"{prefix}_absolute_available"].mean()
        ),
        "constrained_opportunity_rate": float(available.mean()),
        "mean_total_position_uplift": float(
            (
                frame[f"{prefix}_constrained_share_delta_rate"].astype(float)
                * 0.05
            ).mean()
        ),
        "median_conditional_sleeve_share_delta_rate": (
            float(conditional.median()) if len(conditional) else None
        ),
        "median_time_to_reentry_sessions": (
            float(
                frame.loc[
                    available, f"{prefix}_constrained_time_to_reentry_sessions"
                ].median()
            )
            if available.any()
            else None
        ),
    }


def _checks(
    summaries: dict[str, dict[str, dict[str, Any]]], contract: dict[str, Any]
) -> dict[str, bool]:
    gate = contract["feasibility_gate"]
    checks = {
        "minimum_total_sparse_events": sum(
            summaries[lane]["base"]["events"] for lane in summaries
        )
        >= gate["minimum_total_sparse_events"],
        "minimum_primary_sparse_events": summaries["PRIMARY"]["base"]["events"]
        >= gate["minimum_primary_sparse_events"],
        "minimum_independent_sparse_events": summaries[
            "INDEPENDENT_CURRENT_CONSTITUENTS"
        ]["base"]["events"]
        >= gate["minimum_independent_sparse_events"],
    }
    for lane, costs in summaries.items():
        for scenario, values in costs.items():
            suffix = f"{lane.lower()}_{scenario}"
            checks[f"{suffix}_minimum_opportunity_rate"] = (
                values["constrained_opportunity_rate"]
                >= gate["minimum_constrained_opportunity_rate_each_universe"]
            )
            checks[f"{suffix}_minimum_mean_uplift"] = (
                values["mean_total_position_uplift"]
                >= gate["minimum_mean_total_position_uplift_each_universe"]
            )
            median = values["median_conditional_sleeve_share_delta_rate"]
            checks[f"{suffix}_minimum_median_sleeve_delta"] = (
                median is not None
                and median
                >= gate[
                    "minimum_median_conditional_sleeve_share_delta_rate_each_universe"
                ]
            )
    return checks


def build_ceiling(
    output_path: Path = OUTPUT_PATH, report_path: Path = REPORT_PATH
) -> dict[str, Any]:
    contract = validate_contract(json.loads(CONTRACT_PATH.read_text()))
    entries = _load_rush_entries()
    sources = _price_sources()
    frames: dict[str, pd.DataFrame] = {}
    records = []
    failures: dict[str, str] = {}
    for row in entries.itertuples(index=False):
        try:
            if row.ticker not in frames:
                path, expected = sources[row.ticker]
                frames[row.ticker] = _adjusted_prices(path, expected)
            measured = measure_entry(frames[row.ticker], row.signal_date, contract)
            if measured is not None:
                records.append(
                    {
                        "ticker": row.ticker,
                        "universe_role": row.universe_role,
                        "signal_date": row.signal_date.date().isoformat(),
                        "HERD_STATE": float(row.HERD_STATE),
                        "ticker_year_ordinal": int(row.ticker_year_ordinal),
                        "sparse_eligible": bool(row.sparse_eligible),
                        **measured,
                    }
                )
        except Exception as exc:
            failures[f"{row.ticker}:{row.signal_date.date()}"] = (
                f"{type(exc).__name__}: {exc}"
            )
    result = pd.DataFrame(records)
    if result.empty:
        raise OpportunityCeilingError("no evaluable S1 Rush entries")
    sparse = result[result["sparse_eligible"]].copy()
    summaries = {
        lane: {
            scenario: _summary(frame, scenario)
            for scenario in ("base", "stress")
        }
        for lane, frame in sparse.groupby("universe_role", sort=False)
    }
    expected_lanes = set(contract["event"]["universes_reported_separately"])
    if set(summaries) != expected_lanes:
        raise OpportunityCeilingError("one preregistered universe is missing")
    checks = _checks(summaries, contract)
    passed = all(checks.values())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    report = {
        "report_version": VERSION,
        "status": (
            "ECONOMIC_OPPORTUNITY_CEILING_PASSED"
            if passed
            else "ECONOMIC_OPPORTUNITY_CEILING_FAILED"
        ),
        "all_rush_entries": len(result),
        "sparse_entries": len(sparse),
        "tickers": int(result["ticker"].nunique()),
        "summaries": summaries,
        "checks": checks,
        "passed": passed,
        "interpretation": (
            "Non-executable upper bound. Passing only permits success-label V2 design."
        ),
        "direction_evidence_admitted": False,
        "trim_or_reentry_authorized": False,
        "survivorship_safe": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
        "failures": failures,
        "events_path": str(output_path.relative_to(ROOT)),
        "events_sha256": _hash(output_path),
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(build_ceiling(), indent=2))
