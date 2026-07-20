"""PIT 구성 불확실성이 OOS 후보 비교 결론을 바꾸는지 측정한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from math import sqrt
from pathlib import Path

import numpy as np
import pandas as pd

from herd.walk_forward_artifacts import verify_walk_forward_run

FORMAT_VERSION = "herd-pit-sensitivity-evaluation-v1"
TRADING_DAYS = 252
MATERIAL_EXCESS_CAGR_RANGE = 0.005


class PitSensitivityEvaluationError(RuntimeError):
    pass


def _read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_scenarios(path: Path) -> dict:
    root = Path(path)
    manifest = json.loads(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    if manifest.get("format_version") != (
        "herd-pit-uncertainty-scenarios-v1"
    ):
        raise PitSensitivityEvaluationError("unsupported scenario format")
    if manifest.get("policy", {}).get("survivorship_safe") is not False:
        raise PitSensitivityEvaluationError("scenario was improperly promoted")
    for name, metadata in manifest.get("artifacts", {}).items():
        artifact = root / name
        if (
            not artifact.is_file()
            or artifact.stat().st_size != metadata["bytes"]
            or _sha256(artifact) != metadata["sha256"]
        ):
            raise PitSensitivityEvaluationError(
                f"scenario artifact changed: {name}"
            )
    return manifest


def membership_intervals(
    baselines: list[dict],
    changes: list[dict],
    *,
    period_start: str,
    period_end: str,
) -> dict[str, dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]]]:
    scenario_baselines: dict[str, set[str]] = defaultdict(set)
    for row in baselines:
        scenario_baselines[row["scenario"]].add(row["ticker"].upper())
    scenario_changes: dict[str, list[dict]] = defaultdict(list)
    for row in changes:
        scenario_changes[row["scenario"]].append(row)

    start = pd.Timestamp(period_start)
    end_exclusive = pd.Timestamp(period_end) + pd.Timedelta(days=1)
    result = {}
    for scenario, baseline in scenario_baselines.items():
        open_since = {ticker: start for ticker in baseline}
        intervals: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]] = (
            defaultdict(list)
        )
        for row in sorted(
            scenario_changes.get(scenario, []),
            key=lambda value: value["effective_date"],
        ):
            effective = pd.Timestamp(row["effective_date"])
            removed = {
                ticker for ticker in row["removed"].split("|") if ticker
            }
            added = {
                ticker for ticker in row["added"].split("|") if ticker
            }
            for ticker in removed:
                if ticker not in open_since:
                    raise PitSensitivityEvaluationError(
                        f"{scenario}: remove absent ticker {ticker}"
                    )
                intervals[ticker].append(
                    (open_since.pop(ticker), effective)
                )
            for ticker in added:
                if ticker in open_since:
                    raise PitSensitivityEvaluationError(
                        f"{scenario}: add existing ticker {ticker}"
                    )
                open_since[ticker] = effective
        for ticker, opened in open_since.items():
            intervals[ticker].append((opened, end_exclusive))
        result[scenario] = dict(intervals)
    return result


def _membership_mask(
    dates: pd.Series,
    tickers: pd.Series,
    intervals: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]],
) -> pd.Series:
    mask = pd.Series(False, index=dates.index)
    for ticker, positions in tickers.groupby(tickers).groups.items():
        ticker_intervals = intervals.get(str(ticker).upper(), [])
        if not ticker_intervals:
            continue
        ticker_dates = dates.loc[positions]
        eligible = pd.Series(False, index=positions)
        for start, end in ticker_intervals:
            eligible |= (ticker_dates >= start) & (ticker_dates < end)
        mask.loc[positions] = eligible
    return mask


def _drop_exclusion_windows(
    frame: pd.DataFrame,
    exclusions: list[dict],
) -> tuple[pd.DataFrame, int]:
    drop = pd.Series(False, index=frame.index)
    for row in exclusions:
        ticker_rows = frame[
            frame["ticker"].eq(row["ticker"])
        ].sort_values("date")
        if ticker_rows.empty:
            continue
        center = pd.Timestamp(row["center_date"])
        if (
            center < ticker_rows["date"].iloc[0]
            or center > ticker_rows["date"].iloc[-1]
        ):
            continue
        insertion = int(ticker_rows["date"].searchsorted(center))
        before = int(row["observations_before"])
        after = int(row["observations_after"])
        selected = ticker_rows.iloc[
            max(0, insertion - before):min(
                len(ticker_rows), insertion + after + 1
            )
        ].index
        drop.loc[selected] = True
    return frame.loc[~drop].copy(), int(drop.sum())


def _portfolio_daily(frame: pd.DataFrame) -> pd.DataFrame:
    duplicated = frame.duplicated(["candidate", "ticker", "date"])
    if duplicated.any():
        raise PitSensitivityEvaluationError(
            "duplicate candidate/ticker/date returns"
        )
    return (
        frame.groupby(["candidate", "date"], as_index=False)
        .agg(
            strategy_return=("strategy_return", "mean"),
            benchmark_return=("benchmark_return", "mean"),
            eligible_tickers=("ticker", "nunique"),
        )
        .sort_values(["candidate", "date"])
    )


def _return_metrics(returns: pd.Series) -> dict:
    values = returns.astype(float).dropna()
    observations = len(values)
    years = observations / TRADING_DAYS
    total_return = float((1 + values).prod() - 1)
    cagr = (
        float((1 + total_return) ** (1 / years) - 1)
        if years > 0 and total_return > -1
        else None
    )
    wealth = (1 + values).cumprod()
    max_drawdown = float((wealth / wealth.cummax() - 1).min())
    downside = values[values < 0]
    downside_deviation = (
        float(downside.std(ddof=0) * sqrt(TRADING_DAYS))
        if len(downside)
        else 0.0
    )
    annual_return = float(values.mean() * TRADING_DAYS)
    sortino = (
        annual_return / downside_deviation
        if downside_deviation > 0
        else None
    )
    calmar = (
        cagr / abs(max_drawdown)
        if cagr is not None and max_drawdown < 0
        else None
    )
    return {
        "observations": observations,
        "cagr": cagr,
        "max_drawdown": max_drawdown,
        "sortino": sortino,
        "calmar": calmar,
    }


def _evaluate_frame(frame: pd.DataFrame) -> dict[str, dict]:
    portfolio = _portfolio_daily(frame)
    output = {}
    for candidate, rows in portfolio.groupby("candidate"):
        strategy = _return_metrics(rows["strategy_return"])
        benchmark = _return_metrics(rows["benchmark_return"])
        strategy["excess_cagr"] = (
            strategy["cagr"] - benchmark["cagr"]
            if strategy["cagr"] is not None
            and benchmark["cagr"] is not None
            else None
        )
        output[str(candidate)] = {
            "strategy": strategy,
            "benchmark": benchmark,
            "median_eligible_tickers": float(
                rows["eligible_tickers"].median()
            ),
            "minimum_eligible_tickers": int(
                rows["eligible_tickers"].min()
            ),
        }
    return output


def _conclusion(scenarios: dict[str, dict[str, dict]]) -> dict:
    rankings = {}
    candidates = sorted(
        set.intersection(
            *(set(result) for result in scenarios.values())
        )
    )
    for scenario, result in scenarios.items():
        rankings[scenario] = sorted(
            candidates,
            key=lambda candidate: (
                result[candidate]["strategy"]["excess_cagr"],
                candidate,
            ),
            reverse=True,
        )
    ranges = {}
    sign_flips = {}
    for candidate in candidates:
        values = [
            result[candidate]["strategy"]["excess_cagr"]
            for result in scenarios.values()
        ]
        ranges[candidate] = float(max(values) - min(values))
        sign_flips[candidate] = min(values) < 0 < max(values)
    ranking_stable = len({tuple(value) for value in rankings.values()}) == 1
    material_candidates = sorted(
        candidate
        for candidate, value in ranges.items()
        if value > MATERIAL_EXCESS_CAGR_RANGE
    )
    sensitive = (
        not ranking_stable
        or bool(material_candidates)
        or any(sign_flips.values())
    )
    return {
        "ranking_by_scenario": rankings,
        "ranking_stable": ranking_stable,
        "excess_cagr_range_by_candidate": ranges,
        "sign_flip_by_candidate": sign_flips,
        "materiality_threshold": MATERIAL_EXCESS_CAGR_RANGE,
        "material_candidates": material_candidates,
        "decision_sensitive": sensitive,
        "next_action": (
            "RESOLVE_BLOCKERS_OR_EXPAND_PRICE_COVERAGE"
            if sensitive
            else "PROCEED_TO_LEGACY_MODEL_REEVALUATION"
        ),
    }


def evaluate(
    scenario_dir: Path,
    walk_forward_dir: Path,
    output: Path,
) -> dict:
    scenario_root = Path(scenario_dir)
    scenario_manifest = _verify_scenarios(scenario_root)
    walk_manifest = verify_walk_forward_run(Path(walk_forward_dir))
    frame = pd.read_csv(
        Path(walk_forward_dir) / walk_manifest["artifacts"][
            "daily_returns"
        ]["path"]
    )
    required = {
        "candidate",
        "ticker",
        "date",
        "strategy_return",
        "benchmark_return",
    }
    if not required.issubset(frame.columns):
        raise PitSensitivityEvaluationError("daily returns schema mismatch")
    frame["ticker"] = frame["ticker"].str.upper()
    frame["date"] = pd.to_datetime(frame["date"])
    baselines = _read_csv(scenario_root / "scenario_baselines.csv")
    changes = _read_csv(
        scenario_root / "scenario_membership_changes.csv"
    )
    period = scenario_manifest["period"]
    intervals = membership_intervals(
        baselines,
        changes,
        period_start=period["start"],
        period_end=period["end"],
    )
    results = {}
    eligible_counts = {}
    for scenario in scenario_manifest["scenario_order"]:
        selected = frame.loc[
            _membership_mask(
                frame["date"],
                frame["ticker"],
                intervals[scenario],
            )
        ].copy()
        if selected.empty:
            raise PitSensitivityEvaluationError(
                f"{scenario} has no eligible return rows"
            )
        results[scenario] = _evaluate_frame(selected)
        eligible_counts[scenario] = int(selected["ticker"].nunique())

    exclusions = _read_csv(scenario_root / "exclusion_windows.csv")
    assumed = frame.loc[
        _membership_mask(
            frame["date"],
            frame["ticker"],
            intervals["ASSUME_CONTINUITY"],
        )
    ].copy()
    conservative, excluded_rows = _drop_exclusion_windows(
        assumed, exclusions
    )
    results["CONSERVATIVE_EXCLUSION"] = _evaluate_frame(conservative)
    eligible_counts["CONSERVATIVE_EXCLUSION"] = int(
        conservative["ticker"].nunique()
    )

    uncertainty_tickers = sorted(
        {row["ticker"] for row in exclusions}
    )
    covered = sorted(set(frame["ticker"]) & set(uncertainty_tickers))
    report = {
        "format_version": FORMAT_VERSION,
        "sources": {
            "scenario_run_sha256": scenario_manifest["run_sha256"],
            "walk_forward_run_sha256": walk_manifest["run_sha256"],
        },
        "coverage": {
            "walk_forward_tickers": int(frame["ticker"].nunique()),
            "uncertainty_tickers": uncertainty_tickers,
            "covered_uncertainty_tickers": covered,
            "missing_uncertainty_tickers": sorted(
                set(uncertainty_tickers) - set(covered)
            ),
            "eligible_tickers_by_scenario": eligible_counts,
            "conservative_excluded_rows": excluded_rows,
        },
        "scenarios": results,
        "conclusion": _conclusion(results),
        "policy": {
            "research_only": True,
            "survivorship_safe": False,
            "final_adoption_allowed": False,
        },
    }
    target = Path(output)
    if target.exists():
        raise PitSensitivityEvaluationError(
            f"output already exists: {target}"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario_dir", type=Path)
    parser.add_argument("walk_forward_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = evaluate(
        args.scenario_dir,
        args.walk_forward_dir,
        args.output,
    )
    print(json.dumps(report["conclusion"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
