"""세 기대 훼손 증거군을 서로 섞지 않고 장기 OOS에서 검증한다."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest


PROTOCOL = Path(__file__).with_suffix(".json")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_prices(snapshot: Path, tickers: set[str]) -> tuple[dict[str, pd.DataFrame], dict]:
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    frames = {}
    for ticker in sorted(tickers & set(manifest["files"])):
        item = manifest["files"][ticker]
        with gzip.open(snapshot / item["path"], "rt", encoding="utf-8") as stream:
            frame = pd.read_csv(stream, parse_dates=["Date"])
        frames[ticker] = frame.set_index("Date").sort_index()
    return frames, manifest


def _outcome(prices: pd.DataFrame, signal_date: pd.Timestamp, horizon: int,
             ratio: float, cost_bps: float) -> dict | None:
    future = prices.loc[prices.index > signal_date, "Adj Close"].iloc[:horizon + 1]
    if len(future) < horizon + 1:
        return None
    entry = float(future.iloc[0])
    path = future.iloc[1:].astype(float) / entry - 1.0
    terminal = float(path.iloc[-1])
    cost = ratio * cost_bps / 10_000.0
    return {
        "execution_date": future.index[0],
        "terminal_return": terminal,
        "trim_uplift": -ratio * terminal - cost,
        "drawdown_relief": -ratio * min(float(path.min()), 0.0) - cost,
    }


def _holm(rows: list[dict]) -> None:
    ordered = sorted(enumerate(rows), key=lambda item: item[1]["raw_p_value"])
    running = 0.0
    total = len(rows)
    adjusted = [1.0] * total
    for rank, (index, row) in enumerate(ordered):
        running = max(running, min(1.0, row["raw_p_value"] * (total - rank)))
        adjusted[index] = running
    for row, value in zip(rows, adjusted):
        row["holm_p_value"] = value


def evaluate(panel: pd.DataFrame, folds: pd.DataFrame,
             prices: dict[str, pd.DataFrame], protocol: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    panel = panel.copy()
    panel["month_end"] = pd.to_datetime(panel["month_end"])
    events: list[dict] = []
    summaries: list[dict] = []
    q = float(protocol["train_tail_quantile"])
    for family, measurements in protocol["families"].items():
        for measurement, direction in measurements.items():
            fold_values: dict[str, list[float]] = {}
            thresholds: dict[str, float] = {}
            last_event: dict[tuple[str, str], pd.Timestamp] = {}
            for fold in folds.to_dict("records"):
                fold_id = str(fold["fold_id"])
                train = panel.loc[
                    panel["month_end"].between(fold["train_start"], fold["train_end"]), measurement
                ].dropna()
                if len(train) < 100:
                    continue
                threshold = float(train.quantile(q if direction == "LOWER" else 1.0 - q))
                thresholds[fold_id] = threshold
                test = panel.loc[panel["month_end"].between(fold["test_start"], fold["test_end"])].sort_values(["ticker", "month_end"])
                selected = test[measurement].le(threshold) if direction == "LOWER" else test[measurement].ge(threshold)
                previous = test.groupby("ticker")[measurement].shift(1)
                previous_selected = previous.le(threshold) if direction == "LOWER" else previous.ge(threshold)
                test = test.loc[selected & ~previous_selected.fillna(False)]
                for row in test.itertuples(index=False):
                    ticker = str(row.ticker)
                    key = (fold_id, ticker)
                    if key in last_event and (row.month_end - last_event[key]).days < 90:
                        continue
                    result = _outcome(
                        prices.get(ticker, pd.DataFrame()), row.month_end,
                        int(protocol["horizon_sessions"]), float(protocol["trim_ratio"]),
                        float(protocol["one_way_cost_bps"]),
                    ) if ticker in prices else None
                    if result is None:
                        continue
                    last_event[key] = row.month_end
                    event = {
                        "family": family, "measurement": measurement,
                        "direction": direction, "fold_id": fold_id, "ticker": ticker,
                        "signal_date": row.month_end, "threshold": threshold,
                        "measurement_value": float(getattr(row, measurement)), **result,
                    }
                    events.append(event)
                    fold_values.setdefault(fold_id, []).append(result["trim_uplift"])
            subset = [event for event in events if event["family"] == family and event["measurement"] == measurement]
            uplift = [event["trim_uplift"] for event in subset]
            relief = [event["drawdown_relief"] for event in subset]
            fold_medians = {key: float(np.median(value)) for key, value in fold_values.items()}
            positives = sum(value > 0 for value in fold_medians.values())
            raw_p = float(binomtest(positives, len(fold_medians), 0.5, alternative="greater").pvalue) if fold_medians else 1.0
            summaries.append({
                "family": family, "measurement": measurement, "direction": direction,
                "events": len(subset), "tickers": len({event["ticker"] for event in subset}),
                "eligible_folds": len(fold_medians), "positive_folds": positives,
                "median_trim_uplift": float(np.median(uplift)) if uplift else None,
                "median_drawdown_relief": float(np.median(relief)) if relief else None,
                "raw_p_value": raw_p,
                "thresholds_json": json.dumps(thresholds, sort_keys=True, separators=(",", ":")),
                "fold_medians_json": json.dumps(fold_medians, sort_keys=True, separators=(",", ":")),
            })
    _holm(summaries)
    gate = protocol["gate"]
    for row in summaries:
        row["decision"] = "PASS_INDEPENDENT_EVIDENCE" if (
            row["events"] >= gate["minimum_events"]
            and row["tickers"] >= gate["minimum_tickers"]
            and row["eligible_folds"] >= gate["minimum_eligible_folds"]
            and row["positive_folds"] >= gate["minimum_positive_folds"]
            and row["median_trim_uplift"] is not None
            and row["median_trim_uplift"] > gate["minimum_median_trim_uplift"]
            and row["median_drawdown_relief"] >= gate["minimum_median_drawdown_relief"]
            and row["holm_p_value"] <= gate["maximum_holm_p_value"]
        ) else "REJECTED_INDEPENDENT_EVIDENCE"
    family_decisions = {}
    for family in protocol["families"]:
        passed = [row["measurement"] for row in summaries if row["family"] == family and row["decision"].startswith("PASS")]
        family_decisions[family] = {"decision": "PASS" if passed else "REJECTED", "passed_measurements": passed}
    report = {
        "report_version": "herd-expectation-evidence-oos-v1",
        "status": "RESEARCH_ONLY",
        "families": family_decisions,
        "passed_evidence_count": sum(len(value["passed_measurements"]) for value in family_decisions.values()),
        "operational_sell_authority": False,
        "operational_action_ratio": 0.0,
        "survivorship_safe": False,
        "limitations": [
            "The fixed large-cap universe remains survivorship-biased.",
            "Yahoo adjusted prices are a public-research input, not an exchange-grade total-return source.",
            "A passing measurement still requires preregistered combination and completed-cycle validation."
        ],
    }
    return pd.DataFrame(events), pd.DataFrame(summaries), report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-events", type=Path, required=True)
    parser.add_argument("--output-comparison", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    panel_path, snapshot, folds_path = Path(protocol["input_panel"]), Path(protocol["snapshot"]), Path(protocol["folds"])
    panel = pd.read_csv(panel_path)
    prices, manifest = _load_prices(snapshot, set(panel["ticker"].astype(str)))
    events, comparison, report = evaluate(panel, pd.read_csv(folds_path), prices, protocol)
    args.output_events.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(args.output_events, index=False, float_format="%.12g", lineterminator="\n")
    comparison.to_csv(args.output_comparison, index=False, float_format="%.12g", lineterminator="\n")
    report.update({
        "protocol_sha256": _sha256(PROTOCOL), "input_sha256": _sha256(panel_path),
        "folds_sha256": _sha256(folds_path), "snapshot_id": manifest["snapshot_id"],
        "snapshot_sha256": manifest["snapshot_sha256"],
    })
    args.output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
