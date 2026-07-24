"""13F 느린 군중 맥락의 Rush BREAKING 대비 독립 OOS 증분을 검증한다."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np
import pandas as pd

from herd.long_price_snapshot import verify_snapshot
from herd.sec_13f_security_ledger_v1 import ROOT, sha256
from herd.vnext_competing_path_economic_label_v1 import (
    classify_competing_path,
    load_contract as load_label_contract,
)


CONTRACT = ROOT / "data/herd/sec_13f_crowding_incremental_oos_v1.json"
CONTEXT = ROOT / "data/reports/sec_13f_slow_context_v1.csv"
TRANSITION_PANEL = (
    ROOT
    / "data/walk_forward/herd-transition-s1/"
    "independent_current_constituents.csv.gz"
)
SNAPSHOT = ROOT / "data/snapshots/yf-independent-current-sp500-20260721"
PANEL = ROOT / "data/reports/sec_13f_crowding_incremental_panel_v1.csv"
FOLDS = ROOT / "data/reports/sec_13f_crowding_incremental_folds_v1.csv"
REPORT = ROOT / "data/reports/sec_13f_crowding_incremental_oos_v1.json"
FORMAT_VERSION = "SEC_13F_CROWDING_INCREMENTAL_OOS_V1"


class Sec13fCrowdingOosError(RuntimeError):
    """13F 증분 가설의 사전등록·PIT·OOS 경계 위반 시 발생한다."""


@dataclass(frozen=True)
class FittedSingleFeature:
    intercept: float
    coefficient: float
    converged: bool


def _verify_pinned_inputs(contract: dict[str, Any]) -> dict[str, Any]:
    payloads = {}
    for item in contract["pinned_inputs"]:
        path = ROOT / item["path"]
        if not path.is_file() or sha256(path) != item["sha256"]:
            raise Sec13fCrowdingOosError(
                f"pinned OOS input changed: {item['path']}"
            )
        payload = json.loads(path.read_text(encoding="utf-8"))
        status = payload.get("status", payload.get("contract_version"))
        if status != item["required_status"]:
            raise Sec13fCrowdingOosError(
                f"pinned OOS input status changed: {item['path']}"
            )
        payloads[item["path"]] = payload
    return payloads


def _validate_contract(contract: dict[str, Any]) -> None:
    if (
        contract.get("protocol_version") != FORMAT_VERSION
        or contract.get("status") != "LOCKED_BEFORE_13F_DIRECTION_OUTCOMES"
    ):
        raise Sec13fCrowdingOosError("13F OOS protocol is not locked")
    if contract["single_hypothesis"]["tested_context_count"] != 1:
        raise Sec13fCrowdingOosError("only one 13F context may be tested")
    model = contract["model"]
    if (
        model["l2_penalty"] != 1.0
        or model["hyperparameter_or_threshold_search"]
        or model["probability_cutoff_authorizes_action"]
    ):
        raise Sec13fCrowdingOosError("13F model boundary was weakened")
    folds = contract["folds"]
    if [fold["id"] for fold in folds] != ["F1", "F2", "F3", "F4"]:
        raise Sec13fCrowdingOosError("13F OOS folds changed")
    for prior, current in zip(folds, folds[1:]):
        if pd.Timestamp(prior["test_end"]) >= pd.Timestamp(
            current["test_start"]
        ):
            raise Sec13fCrowdingOosError("13F OOS test folds overlap")
    firewall = contract["research_firewall"]
    if (
        firewall["standalone_13f_action_allowed"]
        or firewall["herd_weight_change_allowed"]
        or firewall["operational_action_ratio"] != 0.0
        or firewall["blind_holdout_access"]
    ):
        raise Sec13fCrowdingOosError("13F research firewall changed")


def context_scores(context: pd.DataFrame) -> pd.DataFrame:
    frame = context.copy()
    frame["context_available_date"] = pd.to_datetime(
        frame["context_available_date"]
    )
    usable = frame["feature_usable"].astype(str).str.lower().eq("true")
    breadth = pd.to_numeric(
        frame["breadth_change_fraction_1q"], errors="coerce"
    )
    concentration = pd.to_numeric(
        frame["top5_concentration_change_1q"], errors="coerce"
    )
    frame["breadth_unwind_percentile"] = (
        (-breadth).where(usable).groupby(frame["context_available_date"]).rank(
            pct=True,
            method="average",
        )
    )
    frame["concentration_rise_percentile"] = (
        concentration.where(usable)
        .groupby(frame["context_available_date"])
        .rank(pct=True, method="average")
    )
    conjunction = usable & breadth.lt(0) & concentration.gt(0)
    frame["crowding_unwind_concentration_score"] = np.where(
        conjunction,
        np.minimum(
            frame["breadth_unwind_percentile"],
            frame["concentration_rise_percentile"],
        ),
        0.0,
    )
    frame["context_measurement_available"] = (
        usable & breadth.notna() & concentration.notna()
    )
    return frame


def _transition_events(
    transition_path: Path,
    cooldown_weeks: int,
) -> pd.DataFrame:
    panel = pd.read_csv(
        transition_path,
        compression="gzip",
        parse_dates=["signal_date", "last_observed_session"],
    )
    event_flag = panel["TRANSITION_EVENT"].astype(str).str.lower().eq("true")
    candidates = panel[
        event_flag & panel["HERD_TRANSITION"].eq("BREAKING")
    ].copy()
    selected = []
    cooldown = pd.Timedelta(weeks=cooldown_weeks)
    for ticker, rows in candidates.groupby("ticker", sort=True):
        last_accepted = None
        for row in rows.sort_values("signal_date").itertuples(index=False):
            if (
                last_accepted is not None
                and row.signal_date - last_accepted < cooldown
            ):
                continue
            selected.append(row._asdict())
            last_accepted = row.signal_date
    events = pd.DataFrame(selected).sort_values(
        ["signal_date", "ticker"]
    ).reset_index(drop=True)
    events["event_id"] = [
        f"13FC-{index:05d}" for index in range(1, len(events) + 1)
    ]
    return events


def attach_context(
    events: pd.DataFrame,
    context: pd.DataFrame,
    maximum_age_days: int,
) -> pd.DataFrame:
    columns = [
        "ticker",
        "report_period",
        "context_available_date",
        "reporting_manager_breadth",
        "breadth_change_fraction_1q",
        "top5_reported_share_concentration",
        "top5_concentration_change_1q",
        "reported_share_hhi",
        "crowding_unwind_concentration_score",
        "context_measurement_available",
    ]
    parts = []
    for ticker, ticker_events in events.groupby("ticker", sort=False):
        ticker_context = context[context["ticker"] == ticker][columns].copy()
        if ticker_context.empty:
            part = ticker_events.copy()
            for column in columns[1:]:
                part[column] = np.nan
            parts.append(part)
            continue
        part = pd.merge_asof(
            ticker_events.sort_values("signal_date"),
            ticker_context.sort_values("context_available_date"),
            left_on="signal_date",
            right_on="context_available_date",
            direction="backward",
        )
        part["ticker"] = ticker
        parts.append(part)
    merged = pd.concat(parts, ignore_index=True)
    merged["context_available_date"] = pd.to_datetime(
        merged["context_available_date"],
        errors="coerce",
    )
    merged["context_age_days"] = (
        merged["signal_date"] - merged["context_available_date"]
    ).dt.days
    measurement = (
        merged["context_measurement_available"]
        .fillna(False)
        .astype(bool)
    )
    merged["context_eligible"] = (
        measurement
        & merged["context_available_date"].notna()
        & merged["context_available_date"].le(merged["signal_date"])
        & merged["context_age_days"].between(0, maximum_age_days)
    )
    return merged.sort_values(["signal_date", "ticker"]).reset_index(drop=True)


def _read_price_frames(snapshot: Path, tickers: set[str]) -> dict[str, pd.DataFrame]:
    manifest = verify_snapshot(snapshot)
    missing = sorted(tickers - set(manifest["files"]))
    if missing:
        raise Sec13fCrowdingOosError(
            f"independent snapshot missing tickers: {missing[:5]}"
        )
    frames = {}
    for ticker in sorted(tickers):
        item = manifest["files"][ticker]
        path = snapshot / item["path"]
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8") as handle:
            frames[ticker] = pd.read_csv(
                handle,
                parse_dates=["Date"],
            ).set_index("Date")
    return frames


def attach_outcomes(
    events: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    contract: dict[str, Any],
) -> pd.DataFrame:
    label_contract = load_label_contract()
    positive = set(contract["target"]["positive"])
    negative = set(contract["target"]["negative"])
    outcomes = []
    for row in events.itertuples(index=False):
        outcome = classify_competing_path(
            frames[row.ticker],
            row.last_observed_session,
            label_contract,
        )
        target = (
            1.0
            if outcome.terminal_path in positive
            else 0.0
            if outcome.terminal_path in negative
            else np.nan
        )
        outcomes.append(
            {
                "event_id": row.event_id,
                "first_boundary": outcome.first_boundary,
                "path_label": outcome.terminal_path,
                "outcome_end": outcome.outcome_end,
                "maximum_favorable_excursion": (
                    outcome.maximum_favorable_excursion
                ),
                "maximum_adverse_excursion": (
                    outcome.maximum_adverse_excursion
                ),
                "terminal_return": outcome.terminal_return,
                "target": target,
            }
        )
    return events.merge(
        pd.DataFrame(outcomes),
        on="event_id",
        validate="one_to_one",
    )


def fit_single_feature(
    score: np.ndarray,
    target: np.ndarray,
    *,
    penalty: float,
    maximum_iterations: int,
    tolerance: float,
) -> FittedSingleFeature:
    x = np.column_stack([np.ones(len(score)), score.astype(float)])
    y = target.astype(float)
    if len(y) == 0 or set(np.unique(y)) != {0.0, 1.0}:
        raise Sec13fCrowdingOosError("training fold requires both classes")
    beta = np.zeros(2, dtype=float)
    regularizer = np.diag([0.0, penalty])
    for _ in range(maximum_iterations):
        logits = np.clip(x @ beta, -35, 35)
        probability = 1.0 / (1.0 + np.exp(-logits))
        weights = np.clip(probability * (1 - probability), 1e-8, None)
        gradient = x.T @ (probability - y) + regularizer @ beta
        hessian = x.T @ (x * weights[:, None]) + regularizer
        step = np.linalg.lstsq(hessian, gradient, rcond=None)[0]
        next_beta = beta - step
        if float(np.max(np.abs(next_beta - beta))) < tolerance:
            return FittedSingleFeature(
                intercept=float(next_beta[0]),
                coefficient=float(next_beta[1]),
                converged=True,
            )
        beta = next_beta
    raise Sec13fCrowdingOosError("fixed single-feature model did not converge")


def _predict(model: FittedSingleFeature, score: np.ndarray) -> np.ndarray:
    logits = np.clip(
        model.intercept + model.coefficient * score.astype(float),
        -35,
        35,
    )
    return 1.0 / (1.0 + np.exp(-logits))


def _roc_auc(actual: np.ndarray, probability: np.ndarray) -> float:
    positive = actual == 1
    negative = actual == 0
    if not positive.any() or not negative.any():
        raise Sec13fCrowdingOosError("ROC AUC requires both classes")
    ranks = pd.Series(probability).rank(method="average").to_numpy()
    positives = int(positive.sum())
    negatives = int(negative.sum())
    return float(
        (ranks[positive].sum() - positives * (positives + 1) / 2)
        / (positives * negatives)
    )


def _metrics(actual: np.ndarray, probability: np.ndarray) -> dict[str, float]:
    probability = np.clip(probability.astype(float), 1e-12, 1 - 1e-12)
    actual = actual.astype(float)
    return {
        "roc_auc": _roc_auc(actual, probability),
        "brier": float(np.mean((probability - actual) ** 2)),
        "log_loss": float(
            -np.mean(
                actual * np.log(probability)
                + (1 - actual) * np.log(1 - probability)
            )
        ),
    }


def _fold_frames(
    panel: pd.DataFrame,
    fold: dict[str, str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    test_start = pd.Timestamp(fold["test_start"])
    eligible = panel[
        panel["context_eligible"] & panel["target"].isin([0.0, 1.0])
    ].copy()
    eligible["outcome_end"] = pd.to_datetime(eligible["outcome_end"])
    train = eligible[
        eligible["signal_date"].le(pd.Timestamp(fold["train_end"]))
        & eligible["outcome_end"].lt(test_start)
    ].copy()
    test = eligible[
        eligible["signal_date"].between(
            test_start,
            pd.Timestamp(fold["test_end"]),
        )
    ].copy()
    return train, test


def evaluate_oos(
    panel: pd.DataFrame,
    contract: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    predictions = []
    fold_rows = []
    model_contract = contract["model"]
    score_column = "crowding_unwind_concentration_score"
    for fold in contract["folds"]:
        train, test = _fold_frames(panel, fold)
        if len(test) == 0 or train["target"].nunique() != 2:
            raise Sec13fCrowdingOosError(f"underfilled OOS fold: {fold['id']}")
        model = fit_single_feature(
            train[score_column].to_numpy(),
            train["target"].to_numpy(),
            penalty=float(model_contract["l2_penalty"]),
            maximum_iterations=int(model_contract["maximum_iterations"]),
            tolerance=float(model_contract["convergence_tolerance"]),
        )
        candidate = _predict(model, test[score_column].to_numpy())
        prevalence = float(train["target"].mean())
        baseline = np.full(len(test), prevalence)
        actual = test["target"].to_numpy()
        candidate_metrics = _metrics(actual, candidate)
        baseline_metrics = _metrics(actual, baseline)
        fold_rows.append(
            {
                "fold_id": fold["id"],
                "train_rows": len(train),
                "test_rows": len(test),
                "test_tickers": test["ticker"].nunique(),
                "test_positive": int(actual.sum()),
                "test_negative": int(len(actual) - actual.sum()),
                "train_prevalence": prevalence,
                "candidate_coefficient": model.coefficient,
                "candidate_roc_auc": candidate_metrics["roc_auc"],
                "baseline_roc_auc": baseline_metrics["roc_auc"],
                "incremental_roc_auc": (
                    candidate_metrics["roc_auc"]
                    - baseline_metrics["roc_auc"]
                ),
                "candidate_log_loss": candidate_metrics["log_loss"],
                "baseline_log_loss": baseline_metrics["log_loss"],
                "candidate_minus_baseline_log_loss": (
                    candidate_metrics["log_loss"]
                    - baseline_metrics["log_loss"]
                ),
                "candidate_brier": candidate_metrics["brier"],
                "baseline_brier": baseline_metrics["brier"],
            }
        )
        test_predictions = test[
            [
                "event_id",
                "ticker",
                "signal_date",
                "target",
                score_column,
            ]
        ].copy()
        test_predictions["fold_id"] = fold["id"]
        test_predictions["candidate_probability"] = candidate
        test_predictions["baseline_probability"] = baseline
        predictions.append(test_predictions)
    return pd.concat(predictions, ignore_index=True), pd.DataFrame(fold_rows)


def _cluster_bootstrap_probability(
    predictions: pd.DataFrame,
    samples: int,
    seed: int,
) -> dict[str, Any]:
    tickers = np.asarray(sorted(predictions["ticker"].unique()))
    grouped = {
        ticker: predictions[predictions["ticker"] == ticker]
        for ticker in tickers
    }
    random = np.random.default_rng(seed)
    edges = []
    for _ in range(samples):
        selected = random.choice(tickers, size=len(tickers), replace=True)
        sample = pd.concat(
            [grouped[ticker] for ticker in selected],
            ignore_index=True,
        )
        actual = sample["target"].to_numpy()
        if len(np.unique(actual)) != 2:
            continue
        candidate = _roc_auc(
            actual,
            sample["candidate_probability"].to_numpy(),
        )
        baseline = _roc_auc(
            actual,
            sample["baseline_probability"].to_numpy(),
        )
        edges.append(candidate - baseline)
    if not edges:
        raise Sec13fCrowdingOosError("cluster bootstrap produced no samples")
    values = np.asarray(edges)
    return {
        "samples_requested": samples,
        "samples_valid": len(values),
        "probability_positive_auc_edge": float((values > 0).mean()),
        "median_auc_edge": float(np.median(values)),
        "percentile_2_5": float(np.quantile(values, 0.025)),
        "percentile_97_5": float(np.quantile(values, 0.975)),
    }


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, lineterminator="\n")


def _report(
    contract: dict[str, Any],
    panel: pd.DataFrame,
    predictions: pd.DataFrame,
    folds: pd.DataFrame,
) -> dict[str, Any]:
    gates = contract["gates"]
    actual = predictions["target"].to_numpy()
    candidate = _metrics(
        actual,
        predictions["candidate_probability"].to_numpy(),
    )
    baseline = _metrics(
        actual,
        predictions["baseline_probability"].to_numpy(),
    )
    bootstrap = _cluster_bootstrap_probability(
        predictions,
        int(gates["bootstrap_samples"]),
        int(gates["bootstrap_seed"]),
    )
    event_year = predictions.assign(
        year=pd.to_datetime(predictions["signal_date"]).dt.year
    ).groupby(["ticker", "year"]).size()
    median_events = float(event_year.median()) if len(event_year) else 0.0
    incremental_auc = candidate["roc_auc"] - baseline["roc_auc"]
    log_loss_delta = candidate["log_loss"] - baseline["log_loss"]
    results = {
        "minimum_evaluable_events": (
            len(predictions) >= gates["minimum_evaluable_events"]
        ),
        "minimum_distinct_tickers": (
            predictions["ticker"].nunique()
            >= gates["minimum_distinct_tickers"]
        ),
        "minimum_non_overlapping_folds": (
            folds["fold_id"].nunique()
            >= gates["minimum_non_overlapping_folds"]
        ),
        "minimum_positive_direction_folds": (
            int((folds["incremental_roc_auc"] > 0).sum())
            >= gates["minimum_positive_direction_folds"]
        ),
        "maximum_median_events_per_ticker_year": (
            median_events <= gates["maximum_median_events_per_ticker_year"]
        ),
        "minimum_incremental_roc_auc": (
            incremental_auc >= gates["minimum_incremental_roc_auc"]
        ),
        "maximum_candidate_minus_baseline_log_loss": (
            log_loss_delta
            <= gates["maximum_candidate_minus_baseline_log_loss"]
        ),
        "minimum_ticker_cluster_bootstrap_probability_positive_auc_edge": (
            bootstrap["probability_positive_auc_edge"]
            >= gates[
                "minimum_ticker_cluster_bootstrap_probability_positive_auc_edge"
            ]
        ),
    }
    passed = all(results.values())
    return {
        "report_version": FORMAT_VERSION,
        "status": (
            "SEC_13F_DIRECTION_HYPOTHESIS_PASSED"
            if passed
            else "SEC_13F_DIRECTION_HYPOTHESIS_REJECTED"
        ),
        "decision": (
            "ALLOW_COMPLETED_5_PERCENT_CYCLE_TEST"
            if passed
            else "KEEP_13F_AS_NON_DIRECTIONAL_CONTEXT_ONLY"
        ),
        "panel": {
            "path": PANEL.relative_to(ROOT).as_posix(),
            "sha256": sha256(PANEL),
            "candidate_events": len(panel),
            "context_eligible_events": int(panel["context_eligible"].sum()),
            "path_counts": panel["path_label"].value_counts(
                dropna=False
            ).to_dict(),
        },
        "folds": {
            "path": FOLDS.relative_to(ROOT).as_posix(),
            "sha256": sha256(FOLDS),
            "test_rows": len(predictions),
            "test_tickers": int(predictions["ticker"].nunique()),
            "positive_direction_folds": int(
                (folds["incremental_roc_auc"] > 0).sum()
            ),
            "median_events_per_ticker_year": median_events,
        },
        "aggregate_metrics": {
            "candidate": candidate,
            "baseline": baseline,
            "incremental_roc_auc": incremental_auc,
            "candidate_minus_baseline_log_loss": log_loss_delta,
        },
        "ticker_cluster_bootstrap": bootstrap,
        "gate_results": results,
        "tested_context_count": 1,
        "hyperparameter_search": False,
        "historical_role": "PRE_HOLDOUT_ONLY",
        "survivorship_safe": False,
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
        "next_step": (
            "RUN_COMPLETED_5_PERCENT_CYCLE_AND_COST_STRESS"
            if passed
            else "STOP_13F_DIRECTION_RESEARCH_WITHOUT_RETUNING"
        ),
    }


def generate(
    *,
    contract_path: Path = CONTRACT,
    context_path: Path = CONTEXT,
    transition_path: Path = TRANSITION_PANEL,
    snapshot_path: Path = SNAPSHOT,
    panel_path: Path = PANEL,
    folds_path: Path = FOLDS,
    report_path: Path = REPORT,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    _validate_contract(contract)
    inputs = _verify_pinned_inputs(contract)
    transition_report = inputs["data/reports/herd_transition_s1.json"]
    receipt = transition_report["panels"][
        contract["population"]["role"]
    ]
    if sha256(transition_path) != receipt["sha256"]:
        raise Sec13fCrowdingOosError("transition panel hash changed")
    snapshot_manifest = snapshot_path / "manifest.json"
    if sha256(snapshot_manifest) != (
        json.loads(
            (ROOT / "data/herd/herd_state_s1.json").read_text(encoding="utf-8")
        )["inputs"]["independent_snapshot_manifest"]["sha256"]
    ):
        raise Sec13fCrowdingOosError("independent price manifest changed")

    context = context_scores(pd.read_csv(context_path))
    events = _transition_events(
        transition_path,
        int(contract["population"]["cooldown_weeks"]),
    )
    events = attach_context(
        events,
        context,
        int(contract["context_join"]["maximum_context_age_days"]),
    )
    frames = _read_price_frames(snapshot_path, set(events["ticker"]))
    panel = attach_outcomes(events, frames, contract)
    predictions, folds = evaluate_oos(panel, contract)
    _write_csv(panel_path, panel)
    _write_csv(folds_path, folds)
    report = _report(contract, panel, predictions, folds)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def verify_outputs(report_path: Path = REPORT) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("report_version") != FORMAT_VERSION:
        raise Sec13fCrowdingOosError("unexpected 13F OOS report")
    for key in ("panel", "folds"):
        artifact = report[key]
        path = ROOT / artifact["path"]
        if not path.is_file() or sha256(path) != artifact["sha256"]:
            raise Sec13fCrowdingOosError(f"13F OOS {key} hash changed")
    if report["operational_action_ratio"] != 0.0:
        raise Sec13fCrowdingOosError("13F OOS authorized an action")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    report = verify_outputs() if args.verify_only else generate()
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
