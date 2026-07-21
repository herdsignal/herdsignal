"""사전등록한 차세대 HERD 후보를 결합 없이 독립 walk-forward OOS 검증한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from scipy.stats import binomtest, mannwhitneyu

from herd.herd_candidate_protocol_v2 import load_and_validate


TARGET_COLUMNS = {
    "CONTINUATION_13W": "CONTINUATION_13W",
    "PULLBACK_13W": "PULLBACK_13W",
    "STRUCTURAL_BREAK_26W": "STRUCTURAL_BREAK_26W",
}


def _assign_folds(panel: pd.DataFrame, folds: pd.DataFrame) -> pd.DataFrame:
    parts = []
    dates = pd.to_datetime(panel["signal_date"])
    for fold in folds.itertuples(index=False):
        selected = panel[dates.between(pd.Timestamp(fold.test_start), pd.Timestamp(fold.test_end))].copy()
        selected["fold_id"] = fold.fold_id
        parts.append(selected)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def _holm(rows: list[dict]) -> None:
    ordered = sorted(range(len(rows)), key=lambda index: rows[index]["raw_p_value"])
    running = 0.0
    for rank, index in enumerate(ordered):
        running = max(running, min(1.0, rows[index]["raw_p_value"] * (len(rows) - rank)))
        rows[index]["holm_p_value"] = running


def _groups(feature: str, train: pd.DataFrame, test: pd.DataFrame, quantile: float, protocol: dict):
    if feature == "WEEKLY_RSI_EXTREME":
        return test[test[feature] == 1], test[test[feature] == 0], 1.0
    common = protocol["common"]
    threshold = float(train[feature].quantile(quantile))
    control = float(train[feature].quantile(common["control_training_quantile_maximum"]))
    return test[test[feature] >= threshold], test[test[feature] <= control], threshold


def evaluate(panel: pd.DataFrame, folds: pd.DataFrame, protocol: dict) -> tuple[pd.DataFrame, dict]:
    panel = panel.copy()
    panel["signal_date"] = pd.to_datetime(panel["signal_date"])
    test_panel = _assign_folds(panel, folds)
    common = protocol["common"]
    rows = []
    for hypothesis in protocol["hypotheses"]:
        feature, target = hypothesis["feature"], hypothesis["target"]
        target_column = TARGET_COLUMNS[target]
        quantiles = [1.0] if feature == "WEEKLY_RSI_EXTREME" else common["threshold_training_quantiles"]
        for quantile in quantiles:
            samples = []
            fold_gaps = {}
            thresholds = {}
            for fold in folds.itertuples(index=False):
                train = panel[(panel["signal_date"] <= pd.Timestamp(fold.train_end))].dropna(subset=[feature, target_column])
                test = test_panel[test_panel["fold_id"] == fold.fold_id].dropna(subset=[feature, target_column])
                if len(train) < common["minimum_training_events"] or test.empty:
                    continue
                treatment, control, threshold = _groups(feature, train, test, quantile, protocol)
                if treatment.empty or control.empty:
                    continue
                tagged = pd.concat([treatment.assign(group="TREATMENT"), control.assign(group="CONTROL")])
                samples.append(tagged)
                fold_gaps[fold.fold_id] = float(treatment[target_column].mean() - control[target_column].mean())
                thresholds[fold.fold_id] = threshold
            sample = pd.concat(samples, ignore_index=True) if samples else pd.DataFrame()
            treatment = sample[sample["group"] == "TREATMENT"] if not sample.empty else sample
            control = sample[sample["group"] == "CONTROL"] if not sample.empty else sample
            event_rate = float(treatment[target_column].mean()) if not treatment.empty else None
            control_rate = float(control[target_column].mean()) if not control.empty else None
            if hypothesis["role"] == "REGIME_CONTEXT" and not sample.empty:
                treatment_dates = treatment.groupby("signal_date")[target_column].mean()
                control_dates = control.groupby("signal_date")[target_column].mean()
                p_value = float(mannwhitneyu(treatment_dates, control_dates, alternative="greater").pvalue)
                signal_dates = len(treatment_dates) + len(control_dates)
            else:
                date_gaps = []
                if not sample.empty:
                    for _, date_rows in sample.groupby("signal_date"):
                        left = date_rows[date_rows["group"] == "TREATMENT"][target_column]
                        right = date_rows[date_rows["group"] == "CONTROL"][target_column]
                        if not left.empty and not right.empty:
                            date_gaps.append(float(left.mean() - right.mean()))
                positive = sum(value > 0 for value in date_gaps)
                negative = sum(value < 0 for value in date_gaps)
                p_value = float(binomtest(positive, positive + negative, .5, alternative="greater").pvalue) if positive + negative else 1.0
                signal_dates = len(date_gaps)
            rows.append({
                "hypothesis_id":hypothesis["id"], "feature":feature, "target":target,
                "role":hypothesis["role"], "quantile":quantile,
                "treatment_events":len(treatment), "control_events":len(control),
                "tickers":int(treatment["ticker"].nunique()) if not treatment.empty else 0,
                "test_folds":int(treatment["fold_id"].nunique()) if not treatment.empty else 0,
                "directional_folds":sum(value > 0 for value in fold_gaps.values()),
                "signal_dates":signal_dates, "target_rate":event_rate, "control_rate":control_rate,
                "target_rate_gap":event_rate-control_rate if event_rate is not None else None,
                "raw_p_value":p_value, "thresholds":json.dumps(thresholds, sort_keys=True)
            })
    _holm(rows)
    for row in rows:
        role_gate = protocol["adoption_gates"][row["role"]]
        base = (
            row["treatment_events"] >= common["minimum_treatment_events"]
            and row["tickers"] >= common["minimum_tickers"]
            and row["test_folds"] >= common["minimum_test_folds"]
            and row["directional_folds"] >= common["minimum_directional_folds"]
            and row["signal_dates"] >= common["minimum_signal_dates"]
            and row["holm_p_value"] <= common["maximum_holm_p_value"]
        )
        if row["role"] == "REGIME_CONTEXT":
            row["passed"] = bool(base and row["target_rate_gap"] >= role_gate["minimum_interaction_gap"])
            row["direction_authority"] = False
        else:
            row["passed"] = bool(base and row["target_rate"] >= role_gate["minimum_target_rate"] and row["target_rate_gap"] >= role_gate["minimum_control_gap"])
            row["direction_authority"] = bool(row["passed"] and row["role"] in {"PROFIT_TAKE_DIRECTION", "CONTINUATION_SHIELD"})
    table = pd.DataFrame(rows)
    passing = table[table["passed"]]
    report = {
        "report_version":"herd-candidate-oos-v2", "tests":len(table),
        "passing_variants":passing["hypothesis_id"].tolist(),
        "passing_direction_variants":passing[passing["direction_authority"]]["hypothesis_id"].tolist(),
        "profit_take_evidence_ready":bool(((passing["role"] == "PROFIT_TAKE_DIRECTION") & passing["direction_authority"]).any()),
        "continuation_shield_ready":bool(((passing["role"] == "CONTINUATION_SHIELD") & passing["direction_authority"]).any()),
        "weights_allowed":False, "operational_action_ratio":0.0, "blind_holdout_access":False
    }
    return table, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--folds", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    protocol, _ = load_and_validate()
    table, report = evaluate(pd.read_csv(args.features), pd.read_csv(args.folds), protocol)
    table.to_csv(args.summary, index=False)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
