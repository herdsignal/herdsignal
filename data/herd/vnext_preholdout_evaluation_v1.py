"""vNext 결합 가설을 purged expanding OOS와 블록 ablation으로 판정한다."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np
import pandas as pd

from herd.vnext_competing_path_economic_label_v1 import (
    evaluate_trim_counterfactual,
    load_contract as load_label_contract,
)
from herd.vnext_joint_model_v1 import (
    ROOT,
    _read_snapshot_frames,
    fit_joint_model,
    load_protocol as load_joint_protocol,
    predict_joint_probability,
)


PROTOCOL_PATH = Path(__file__).with_suffix(".json")
PROTOCOL_VERSION = "HERD_VNEXT_PREHOLDOUT_EVALUATION_V1"


class VNextPreholdoutError(ValueError):
    """OOS fold·게이트·승격 경계가 완화됐을 때 발생한다."""


def load_protocol(path: Path = PROTOCOL_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_protocol(protocol: dict[str, Any]) -> dict[str, Any]:
    if (
        protocol.get("protocol_version") != PROTOCOL_VERSION
        or protocol.get("status") != "LOCKED_BEFORE_VNEXT_PREHOLDOUT_RESULTS"
    ):
        raise VNextPreholdoutError("preholdout protocol is not locked")
    folds = protocol.get("folds", [])
    if [fold.get("id") for fold in folds] != ["F1", "F2", "F3", "F4"]:
        raise VNextPreholdoutError("walk-forward folds changed")
    for previous, current in zip(folds, folds[1:]):
        if pd.Timestamp(previous["test_end"]) >= pd.Timestamp(current["test_start"]):
            raise VNextPreholdoutError("test folds overlap")
    if (
        protocol.get("purging", {}).get(
            "train_outcome_must_end_before_test_start"
        )
        is not True
        or protocol.get("purging", {}).get("horizon_sessions") != 126
    ):
        raise VNextPreholdoutError("outcome purge was weakened")
    gate = protocol.get("gate", {})
    if (
        gate.get("minimum_aggregate_roc_auc", 0) < 0.60
        or gate.get("minimum_median_fold_roc_auc", 0) < 0.55
        or gate.get("minimum_directional_folds", 0) < 3
        or gate.get("maximum_ablation_log_loss_advantage", 1) > 0.01
    ):
        raise VNextPreholdoutError("preholdout adoption gate was weakened")
    economic = protocol.get("economic_diagnostic", {})
    if (
        economic.get("trim_fraction") != 0.05
        or economic.get("maximum_candidates_per_ticker_year") != 2
        or economic.get("open_trim_is_success") is not False
        or economic.get("complete_cycle_required_for_promotion") is not True
    ):
        raise VNextPreholdoutError("economic diagnostic boundary changed")
    promotion = protocol.get("promotion_boundary", {})
    if (
        promotion.get("historical_result_is_preholdout_only") is not True
        or promotion.get("complete_cycle_required") is not True
        or promotion.get("prospective_shadow_is_final_blind") is not True
        or promotion.get("operational_action_ratio_before_all_gates") != 0.0
    ):
        raise VNextPreholdoutError("promotion boundary changed")
    return {
        "protocol_version": PROTOCOL_VERSION,
        "locked": True,
        "folds": [fold["id"] for fold in folds],
        "outcome_purge": True,
        "tested_model_count": 1,
        "historical_role": "PRE_HOLDOUT_ONLY",
        "operational_action_ratio": 0.0,
    }


def _roc_auc(actual: np.ndarray, probability: np.ndarray) -> float:
    positive = actual == 1
    negative = actual == 0
    if not positive.any() or not negative.any():
        raise VNextPreholdoutError("ROC AUC requires both classes")
    ranks = pd.Series(probability).rank(method="average").to_numpy()
    count_positive = int(positive.sum())
    count_negative = int(negative.sum())
    return float(
        (
            ranks[positive].sum()
            - count_positive * (count_positive + 1) / 2
        )
        / (count_positive * count_negative)
    )


def _binary_metrics(
    actual: np.ndarray,
    probability: np.ndarray,
    *,
    threshold: float,
) -> dict[str, float]:
    probability = np.clip(probability.astype(float), 1e-12, 1 - 1e-12)
    actual = actual.astype(float)
    prediction = probability >= threshold
    positive = actual == 1
    negative = actual == 0
    sensitivity = float(prediction[positive].mean())
    specificity = float((~prediction[negative]).mean())
    return {
        "roc_auc": _roc_auc(actual, probability),
        "brier": float(np.mean((probability - actual) ** 2)),
        "log_loss": float(
            -np.mean(
                actual * np.log(probability)
                + (1 - actual) * np.log(1 - probability)
            )
        ),
        "balanced_accuracy": (sensitivity + specificity) / 2,
    }


def _fold_data(
    panel: pd.DataFrame,
    fold: dict[str, str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    test_start = pd.Timestamp(fold["test_start"])
    train = panel[
        (panel["signal_date"] <= pd.Timestamp(fold["train_end"]))
        & (panel["vnext_outcome_end"] < test_start)
        & panel["target"].isin([0.0, 1.0])
    ].copy()
    test = panel[
        panel["signal_date"].between(
            test_start,
            pd.Timestamp(fold["test_end"]),
        )
        & panel["target"].isin([0.0, 1.0])
    ].copy()
    return train, test


def _model_specs(joint_protocol: dict[str, Any]) -> list[tuple[str, str | None, bool]]:
    return [
        ("FULL", None, True),
        ("NO_INTERACTION", None, False),
        (
            "WITHOUT_MARKET_AND_SECTOR_REGIME",
            "MARKET_AND_SECTOR_REGIME",
            True,
        ),
        (
            "WITHOUT_STOCK_EXTENSION_AND_TRANSITION",
            "STOCK_EXTENSION_AND_TRANSITION",
            True,
        ),
        ("WITHOUT_PEER_PARTICIPATION", "PEER_PARTICIPATION", True),
        ("WITHOUT_PIT_BUSINESS_VETO", "PIT_BUSINESS_VETO", True),
    ]


def evaluate_oos(
    panel: pd.DataFrame,
    protocol: dict[str, Any],
    joint_protocol: dict[str, Any],
) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, Any]]:
    validate_protocol(protocol)
    source = panel.copy()
    source["signal_date"] = pd.to_datetime(source["signal_date"])
    source["vnext_outcome_end"] = pd.to_datetime(source["vnext_outcome_end"])
    prediction_parts = []
    fold_rows = []
    minimum = protocol["minimum_fold_data"]

    for fold in protocol["folds"]:
        train, test = _fold_data(source, fold)
        counts = test["target"].value_counts().to_dict()
        if (
            len(test) < minimum["test_rows"]
            or counts.get(1.0, 0) < minimum["positive_rows"]
            or counts.get(0.0, 0) < minimum["negative_rows"]
        ):
            raise VNextPreholdoutError(f"{fold['id']} lacks minimum test data")
        prevalence = float(train["target"].mean())
        model_outputs = {}
        for name, omitted, interaction in _model_specs(joint_protocol):
            model = fit_joint_model(
                train,
                joint_protocol,
                omitted_block=omitted,
                include_interaction=interaction,
            )
            test_probability = predict_joint_probability(model, test)
            model_outputs[name] = test_probability
            metrics = _binary_metrics(
                test["target"].to_numpy(),
                test_probability,
                threshold=prevalence,
            )
            fold_rows.append(
                {
                    "fold_id": fold["id"],
                    "model": name,
                    "train_rows": len(train),
                    "test_rows": len(test),
                    "test_positive": int(counts.get(1.0, 0)),
                    "test_negative": int(counts.get(0.0, 0)),
                    "train_prevalence": prevalence,
                    **metrics,
                }
            )
        baseline_probability = np.full(len(test), prevalence)
        baseline_metrics = _binary_metrics(
            test["target"].to_numpy(),
            baseline_probability,
            threshold=prevalence,
        )
        fold_rows.append(
            {
                "fold_id": fold["id"],
                "model": "TRAIN_PREVALENCE_BASELINE",
                "train_rows": len(train),
                "test_rows": len(test),
                "test_positive": int(counts.get(1.0, 0)),
                "test_negative": int(counts.get(0.0, 0)),
                "train_prevalence": prevalence,
                **baseline_metrics,
            }
        )
        train_model = fit_joint_model(train, joint_protocol)
        train_probability = predict_joint_probability(train_model, train)
        candidate_cutoff = float(np.quantile(train_probability, 0.90))
        output = test[
            [
                "ticker",
                "episode_id",
                "signal_date",
                "last_observed_session",
                "vnext_path_label",
                "target",
            ]
        ].copy()
        output["fold_id"] = fold["id"]
        output["probability"] = model_outputs["FULL"]
        for name, probability in model_outputs.items():
            output[f"probability__{name}"] = probability
        output["train_prevalence"] = prevalence
        output["candidate_cutoff"] = candidate_cutoff
        output["candidate_before_frequency_cap"] = (
            output["probability"] >= candidate_cutoff
        )
        prediction_parts.append(output)

    predictions = pd.concat(prediction_parts, ignore_index=True)
    predictions["year"] = predictions["signal_date"].dt.year
    predictions["economic_candidate"] = False
    eligible = predictions[predictions["candidate_before_frequency_cap"]]
    selected_index = (
        eligible.sort_values("probability", ascending=False)
        .groupby(["ticker", "year"], sort=False)
        .head(protocol["economic_diagnostic"]["maximum_candidates_per_ticker_year"])
        .index
    )
    predictions.loc[selected_index, "economic_candidate"] = True

    folds = pd.DataFrame(fold_rows)
    aggregate = {}
    actual = predictions["target"].to_numpy()
    for name, _, _ in _model_specs(joint_protocol):
        probability = predictions[f"probability__{name}"].to_numpy()
        aggregate[name] = _binary_metrics(
            actual,
            probability,
            threshold=float(predictions["train_prevalence"].median()),
        )
    baseline_rows = folds[folds["model"] == "TRAIN_PREVALENCE_BASELINE"]
    total_test = int(baseline_rows["test_rows"].sum())
    aggregate["TRAIN_PREVALENCE_BASELINE"] = {
        metric: float(
            (baseline_rows[metric] * baseline_rows["test_rows"]).sum() / total_test
        )
        for metric in ("roc_auc", "brier", "log_loss", "balanced_accuracy")
    }

    full_folds = folds[folds["model"] == "FULL"]
    full = aggregate["FULL"]
    baseline = aggregate["TRAIN_PREVALENCE_BASELINE"]
    gate = protocol["gate"]
    ablation_advantages = {
        name: full["log_loss"] - metrics["log_loss"]
        for name, metrics in aggregate.items()
        if name not in {"FULL", "TRAIN_PREVALENCE_BASELINE"}
    }
    checks = {
        "aggregate_roc_auc": full["roc_auc"]
        >= gate["minimum_aggregate_roc_auc"],
        "median_fold_roc_auc": float(median(full_folds["roc_auc"]))
        >= gate["minimum_median_fold_roc_auc"],
        "directional_folds": int((full_folds["roc_auc"] > 0.5).sum())
        >= gate["minimum_directional_folds"],
        "brier_vs_baseline": baseline["brier"] - full["brier"]
        > gate["minimum_brier_improvement_vs_train_prevalence"],
        "log_loss_vs_baseline": baseline["log_loss"] - full["log_loss"]
        > gate["minimum_log_loss_improvement_vs_train_prevalence"],
        "no_ablation_materially_better": max(ablation_advantages.values())
        <= gate["maximum_ablation_log_loss_advantage"],
        "interaction_not_harmful": ablation_advantages["NO_INTERACTION"] <= 0.0,
    }
    summary = {
        "aggregate_metrics": aggregate,
        "ablation_log_loss_advantage_over_full": ablation_advantages,
        "gate_checks": checks,
        "path_model_passed": all(checks.values()),
        "directional_folds": int((full_folds["roc_auc"] > 0.5).sum()),
        "median_fold_roc_auc": float(median(full_folds["roc_auc"])),
        "economic_candidate_count": int(predictions["economic_candidate"].sum()),
    }
    return predictions, fold_rows, summary


def economic_diagnostic(
    predictions: pd.DataFrame,
    protocol: dict[str, Any],
    joint_protocol: dict[str, Any],
) -> dict[str, Any]:
    selected = predictions[predictions["economic_candidate"]]
    tickers = set(selected["ticker"])
    frames = _read_snapshot_frames(
        ROOT / joint_protocol["data_boundary"]["price_snapshot"],
        tickers,
    )
    base_contract = load_label_contract()
    scenarios = {}
    for total_cost in protocol["economic_diagnostic"]["one_way_total_cost_bps"]:
        contract = copy.deepcopy(base_contract)
        contract["economic_label_contract"]["one_way_fee_bps"] = total_cost / 2
        contract["economic_label_contract"]["one_way_slippage_bps"] = total_cost / 2
        relative_edges = []
        for event in selected.itertuples(index=False):
            outcome = evaluate_trim_counterfactual(
                frames[event.ticker],
                pd.Timestamp(event.last_observed_session),
                contract=contract,
            )
            sale_notional = outcome.trim_fraction * outcome.sale_execution_price
            relative_edges.append(
                outcome.open_trim_terminal_wealth_delta / sale_notional
            )
        scenarios[str(total_cost)] = {
            "events": len(relative_edges),
            "positive_open_trim_fraction": (
                float(np.mean(np.asarray(relative_edges) > 0))
                if relative_edges
                else None
            ),
            "median_open_trim_relative_edge": (
                float(np.median(relative_edges)) if relative_edges else None
            ),
            "complete_cycles": 0,
            "promotion_authority": False,
        }
    return {
        "selection": protocol["economic_diagnostic"]["selection"],
        "selected_events": len(selected),
        "scenarios": scenarios,
        "open_trim_is_success": False,
        "complete_cycle_available": False,
    }


def run() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], dict[str, Any]]:
    protocol = load_protocol()
    audit = validate_protocol(protocol)
    joint_protocol = load_joint_protocol()
    panel = pd.read_csv(ROOT / protocol["input_panel"])
    predictions, fold_rows, summary = evaluate_oos(
        panel,
        protocol,
        joint_protocol,
    )
    economics = economic_diagnostic(predictions, protocol, joint_protocol)
    blockers = []
    if not summary["path_model_passed"]:
        blockers.append("PATH_MODEL_PREHOLDOUT_GATE_FAILED")
    blockers.extend(
        [
            "NO_COMPLETE_PROFIT_TAKE_REENTRY_CYCLE",
            "SURVIVORSHIP_SAFE_FALSE",
            "PROSPECTIVE_SHADOW_NOT_STARTED",
        ]
    )
    report = {
        "report_version": "HERD_VNEXT_PREHOLDOUT_EVALUATION_REPORT_V1",
        "status": (
            "PATH_MODEL_PASSED_PREHOLDOUT"
            if summary["path_model_passed"]
            else "PATH_MODEL_REJECTED_PREHOLDOUT"
        ),
        "decision": "NO_ADOPTABLE_CANDIDATE",
        "protocol": audit,
        **summary,
        "economic_diagnostic": economics,
        "overfit_metrics": protocol["overfit_metrics"],
        "promotion_blockers": blockers,
        "historical_role": "PRE_HOLDOUT_ONLY",
        "survivorship_safe": False,
        "prospective_shadow_status": (
            "WAITING_FOR_COMPLETE_CYCLE_AND_SAFE_UNIVERSE"
            if summary["path_model_passed"]
            else "BLOCKED_PATH_MODEL_FAILED"
        ),
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
    }
    return predictions, pd.DataFrame(fold_rows), report, protocol


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--folds", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    predictions, folds, report, _ = run()
    args.predictions.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(args.predictions, index=False)
    folds.to_csv(args.folds, index=False)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
