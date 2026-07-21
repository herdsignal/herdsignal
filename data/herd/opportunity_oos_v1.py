"""장기 승자의 continuation과 tradable pullback 가설을 독립 OOS 검증한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from scipy.stats import binomtest


REGISTRY_PATH = Path(__file__).with_name("opportunity_hypotheses_v1.json")


def validate_registry(registry: dict) -> dict:
    if registry.get("registry_version") != "HERD_OPPORTUNITY_HYPOTHESES_V1" \
            or registry.get("status") != "LOCKED_BEFORE_OOS_RESULTS":
        raise ValueError("opportunity registry is not locked")
    hypotheses = registry.get("hypotheses", [])
    if len(hypotheses) != 7 or len({item["feature"] for item in hypotheses}) != 7:
        raise ValueError("seven independent features are required")
    test = registry["common_test"]
    if test["minimum_test_folds"] < 4 or test["training_thresholds"] != [0.8, 0.9]:
        raise ValueError("OOS gate was weakened")
    if "COMBINE_FEATURES_BEFORE_INDEPENDENT_PASS" not in registry["forbidden"]:
        raise ValueError("premature feature combination is not forbidden")
    return {"registry_version": registry["registry_version"], "hypotheses": 7, "locked": True}


def load_registry(path: Path = REGISTRY_PATH) -> tuple[dict, dict]:
    registry = json.loads(path.read_text(encoding="utf-8"))
    return registry, validate_registry(registry)


def _deduplicate_events(features: pd.DataFrame) -> pd.DataFrame:
    frame = features.copy()
    frame["signal_date"] = pd.to_datetime(frame["signal_date"])
    invariant = ["label", "fold_id"]
    for _, rows in frame.groupby(["ticker", "signal_date"]):
        if any(rows[column].nunique(dropna=False) > 1 for column in invariant):
            raise ValueError("duplicate event sources disagree on path outcome")
    return frame.sort_values(["ticker", "signal_date"]).drop_duplicates(["ticker", "signal_date"])


def _holm(rows: list[dict]) -> None:
    ordered = sorted(range(len(rows)), key=lambda index: rows[index]["raw_p_value"])
    running = 0.0
    for rank, index in enumerate(ordered):
        running = max(running, min(1.0, rows[index]["raw_p_value"] * (len(rows) - rank)))
        rows[index]["holm_p_value"] = running


def evaluate_opportunity_oos(features: pd.DataFrame, folds: pd.DataFrame, registry: dict) -> tuple[pd.DataFrame, dict]:
    events = _deduplicate_events(features)
    common = registry["common_test"]
    rows = []
    for hypothesis in registry["hypotheses"]:
        usable = events.dropna(subset=[hypothesis["feature"]])
        for quantile in common["training_thresholds"]:
            pooled = []
            fold_gaps = {}
            thresholds = {}
            for fold in folds.itertuples(index=False):
                train = usable[usable["signal_date"] <= pd.Timestamp(fold.train_end)]
                test = usable[usable["signal_date"].between(pd.Timestamp(fold.test_start), pd.Timestamp(fold.test_end))].copy()
                if len(train) < common["minimum_training_events"] or test.empty:
                    continue
                treatment_threshold = float(train[hypothesis["feature"]].quantile(quantile))
                control_threshold = float(train[hypothesis["feature"]].quantile(common["control_training_quantile_maximum"]))
                test["group"] = "MIDDLE"
                test.loc[test[hypothesis["feature"]] >= treatment_threshold, "group"] = "TREATMENT"
                test.loc[test[hypothesis["feature"]] <= control_threshold, "group"] = "CONTROL"
                selected = test[test["group"].isin(["TREATMENT", "CONTROL"])].copy()
                if selected.empty:
                    continue
                selected["fold_id_v3"] = fold.fold_id
                selected["target_hit"] = selected["label"] == hypothesis["target_label"]
                left = selected[selected["group"] == "TREATMENT"]["target_hit"]
                right = selected[selected["group"] == "CONTROL"]["target_hit"]
                if not left.empty and not right.empty:
                    fold_gaps[fold.fold_id] = float(left.mean() - right.mean())
                thresholds[fold.fold_id] = treatment_threshold
                pooled.append(selected)
            sample = pd.concat(pooled, ignore_index=True) if pooled else pd.DataFrame()
            treatment = sample[sample["group"] == "TREATMENT"] if not sample.empty else sample
            control = sample[sample["group"] == "CONTROL"] if not sample.empty else sample
            treatment_hits = int(treatment["target_hit"].sum()) if not treatment.empty else 0
            control_hits = int(control["target_hit"].sum()) if not control.empty else 0
            date_gaps = []
            if not sample.empty:
                for _, date_rows in sample.groupby("signal_date"):
                    date_treatment = date_rows[date_rows["group"] == "TREATMENT"]["target_hit"]
                    date_control = date_rows[date_rows["group"] == "CONTROL"]["target_hit"]
                    if not date_treatment.empty and not date_control.empty:
                        date_gaps.append(float(date_treatment.mean() - date_control.mean()))
            positive_dates = sum(value > 0 for value in date_gaps)
            p_value = (
                float(binomtest(positive_dates, len(date_gaps), 0.5, alternative="greater").pvalue)
                if date_gaps else 1.0
            )
            treatment_rate = treatment_hits / len(treatment) if len(treatment) else None
            control_rate = control_hits / len(control) if len(control) else None
            rows.append({
                "hypothesis_id": hypothesis["id"], "role": hypothesis["role"],
                "feature": hypothesis["feature"], "target_label": hypothesis["target_label"],
                "quantile": quantile, "treatment_events": len(treatment), "control_events": len(control),
                "treatment_tickers": treatment["ticker"].nunique() if not treatment.empty else 0,
                "test_folds": sample["fold_id_v3"].nunique() if not sample.empty else 0,
                "directional_folds": sum(value > 0 for value in fold_gaps.values()),
                "comparison_dates": len(date_gaps),
                "directional_dates": positive_dates,
                "treatment_target_rate": treatment_rate, "control_target_rate": control_rate,
                "target_rate_gap": treatment_rate - control_rate if treatment_rate is not None and control_rate is not None else None,
                "raw_p_value": p_value,
                "fold_gaps": json.dumps(fold_gaps, sort_keys=True),
                "fold_thresholds": json.dumps(thresholds, sort_keys=True),
            })
    _holm(rows)
    for row in rows:
        row["passed"] = bool(
            row["treatment_events"] >= common["minimum_treatment_events"]
            and row["treatment_tickers"] >= common["minimum_tickers"]
            and row["comparison_dates"] >= common["minimum_comparison_dates"]
            and row["test_folds"] >= common["minimum_test_folds"]
            and row["directional_folds"] >= common["minimum_directional_folds"]
            and row["target_rate_gap"] is not None and row["target_rate_gap"] >= common["minimum_target_rate_gap"]
            and row["holm_p_value"] <= common["maximum_holm_p_value"]
        )
    table = pd.DataFrame(rows)
    passing = table[table["passed"]] if not table.empty else table
    report = {
        "report_version": "herd-opportunity-oos-v1",
        "deduplicated_events": len(events),
        "passing_hypotheses": sorted(passing["hypothesis_id"].unique()) if not passing.empty else [],
        "passing_continuation_shields": sorted(passing[passing["role"] == "CONTINUATION_SHIELD"]["hypothesis_id"].unique()) if not passing.empty else [],
        "passing_pullback_evidence": sorted(passing[passing["role"] == "PULLBACK_EVIDENCE"]["hypothesis_id"].unique()) if not passing.empty else [],
        "profit_take_cycle_allowed": bool(not passing.empty and (passing["role"] == "PULLBACK_EVIDENCE").any()),
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
    }
    return table, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--folds", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    registry, _ = load_registry()
    table, report = evaluate_opportunity_oos(pd.read_csv(args.features), pd.read_csv(args.folds), registry)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.summary, index=False)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
