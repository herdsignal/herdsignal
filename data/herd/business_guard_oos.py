"""SEC PIT 기업 상태 VETO가 이후 하방을 구분하는지 OOS 검증한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

from herd.business_guard_protocol import load_protocol
from herd.data_snapshot import load_snapshot


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_guard_transitions(features: pd.DataFrame) -> pd.DataFrame:
    frame = features.copy()
    frame["month_end"] = pd.to_datetime(frame["month_end"])
    frame = frame.sort_values(["ticker", "month_end"])
    frame["previous_state"] = frame.groupby("ticker")["guard_state"].shift()
    return frame.loc[
        frame["guard_state"].isin(["PASS", "VETO"])
        & frame["guard_state"].ne(frame["previous_state"])
    ].rename(columns={"month_end": "signal_date"})


def add_outcomes(
    events: pd.DataFrame,
    closes: pd.DataFrame,
    horizon: int,
) -> pd.DataFrame:
    rows = []
    for event in events.itertuples(index=False):
        date = pd.Timestamp(event.signal_date)
        end = date + pd.offsets.MonthEnd(horizon)
        current = closes.loc[closes.index <= date, event.ticker].dropna()
        future = closes.loc[
            (closes.index > date) & (closes.index <= end), event.ticker
        ].dropna()
        if current.empty or future.empty:
            continue
        start_price = float(current.iloc[-1])
        rows.append({
            "signal_date": date,
            "ticker": event.ticker,
            "guard_state": event.guard_state,
            "deterioration_flags": event.deterioration_flags,
            "horizon_months": horizon,
            "outcome_end": end,
            "forward_return": float(future.iloc[-1] / start_price - 1),
            "forward_trough_return": float(future.min() / start_price - 1),
        })
    return pd.DataFrame(rows)


def select_non_overlapping_events(events: pd.DataFrame) -> pd.DataFrame:
    kept = []
    for _, group in events.sort_values("signal_date").groupby(
        ["fold_id", "ticker", "horizon_months"], sort=False
    ):
        last_end = None
        for row in group.itertuples(index=False):
            if last_end is not None and row.signal_date <= last_end:
                continue
            kept.append(row._asdict())
            last_end = row.outcome_end
    return pd.DataFrame(kept, columns=events.columns)


def _holm_adjust(rows: list[dict]) -> None:
    ordered = sorted(enumerate(rows), key=lambda item: item[1]["raw_p_value"])
    running = 0.0
    count = len(rows)
    for rank, (index, row) in enumerate(ordered):
        running = max(running, min(1.0, row["raw_p_value"] * (count - rank)))
        rows[index]["holm_p_value"] = running


def evaluate_oos(
    features: pd.DataFrame,
    price_frames: dict[str, pd.DataFrame],
    folds: list[dict],
    protocol: dict,
) -> tuple[pd.DataFrame, list[dict], dict]:
    closes = pd.concat({
        ticker: frame.assign(
            Date=pd.to_datetime(frame["Date"])
        ).set_index("Date")["Close"]
        for ticker, frame in price_frames.items()
    }, axis=1).sort_index()
    transitions = extract_guard_transitions(features)
    event_frames = []
    for horizon in protocol["predictive_test"]["forward_horizons_months"]:
        outcomes = add_outcomes(transitions, closes, horizon)
        for fold in folds:
            start = pd.Timestamp(fold["test_start"])
            end = pd.Timestamp(fold["test_end"])
            eligible = outcomes.loc[
                outcomes["signal_date"].between(start, end)
                & (outcomes["outcome_end"] <= end)
            ].copy()
            eligible["fold_id"] = fold["fold_id"]
            event_frames.append(eligible)
    events = pd.concat(event_frames, ignore_index=True)
    events = select_non_overlapping_events(events)

    summaries = []
    for horizon in protocol["predictive_test"]["forward_horizons_months"]:
        subset = events.loc[events["horizon_months"] == horizon]
        for outcome in ("forward_return", "forward_trough_return"):
            veto = subset.loc[subset["guard_state"] == "VETO", outcome]
            passed = subset.loc[subset["guard_state"] == "PASS", outcome]
            fold_gaps = {}
            for fold_id, fold_rows in subset.groupby("fold_id"):
                left = fold_rows.loc[
                    fold_rows["guard_state"] == "VETO", outcome
                ]
                right = fold_rows.loc[
                    fold_rows["guard_state"] == "PASS", outcome
                ]
                if not left.empty and not right.empty:
                    fold_gaps[fold_id] = float(right.median() - left.median())
            raw_p = (
                float(mannwhitneyu(
                    veto, passed, alternative="less"
                ).pvalue)
                if not veto.empty and not passed.empty else 1.0
            )
            summaries.append({
                "horizon_months": horizon,
                "outcome": outcome,
                "veto_events": int(len(veto)),
                "pass_events": int(len(passed)),
                "veto_folds": int(
                    subset.loc[
                        subset["guard_state"] == "VETO", "fold_id"
                    ].nunique()
                ),
                "pass_folds": int(
                    subset.loc[
                        subset["guard_state"] == "PASS", "fold_id"
                    ].nunique()
                ),
                "directional_folds": int(sum(gap > 0 for gap in fold_gaps.values())),
                "median_veto": float(veto.median()) if not veto.empty else None,
                "median_pass": float(passed.median()) if not passed.empty else None,
                "pass_minus_veto": (
                    float(passed.median() - veto.median())
                    if not veto.empty and not passed.empty else None
                ),
                "raw_p_value": raw_p,
                "fold_gap_json": json.dumps(
                    fold_gaps, sort_keys=True, separators=(",", ":")
                ),
            })
    _holm_adjust(summaries)
    gate = protocol["adoption_gate"]
    for row in summaries:
        row["outcome_pass"] = (
            row["veto_events"] >= gate["minimum_events_per_side"]
            and row["pass_events"] >= gate["minimum_events_per_side"]
            and row["veto_folds"] >= gate["minimum_test_folds_per_side"]
            and row["pass_folds"] >= gate["minimum_test_folds_per_side"]
            and row["directional_folds"] >= gate["minimum_directional_folds"]
            and row["holm_p_value"] <= gate["maximum_holm_p_value"]
            and row["pass_minus_veto"] is not None
            and row["pass_minus_veto"] > 0
        )
    primary = [
        row for row in summaries
        if row["horizon_months"]
        == protocol["predictive_test"]["primary_horizon_months"]
    ]
    primary_passed = sum(row["outcome_pass"] for row in primary)
    decision = (
        "PASS_TO_ADD_BUY_VETO_ABLATION"
        if primary_passed >= gate["required_primary_outcomes"]
        else "REJECT_BUSINESS_GUARD_PREDICTIVE_EVIDENCE"
    )
    return events, summaries, {
        "report_version": "herd-business-guard-oos-v1",
        "decision": decision,
        "primary_outcomes_passed": primary_passed,
        "primary_outcomes_required": gate["required_primary_outcomes"],
        "transition_counts": {
            state: int((transitions["guard_state"] == state).sum())
            for state in ("PASS", "VETO")
        },
        "excluded_unknown_rows": int(
            (features["guard_state"] == "UNKNOWN").sum()
        ),
        "limitations": [
            "The fixed price universe remains survivorship-biased.",
            "JPM and GS are excluded because the general-company revenue contract is not comparable to bank revenue.",
            "Company Facts may contain filer errors; only as-filed acceptance-time-visible facts are used.",
            "A predictive pass authorizes only an add-buy veto ablation, never a sell signal."
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("features", type=Path)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("folds", type=Path)
    parser.add_argument("event_csv", type=Path)
    parser.add_argument("summary_csv", type=Path)
    parser.add_argument("report_json", type=Path)
    args = parser.parse_args()
    feature_frame = pd.read_csv(args.features)
    price_frames, manifest = load_snapshot(args.snapshot)
    folds = pd.read_csv(args.folds, dtype=str).to_dict("records")
    protocol, protocol_audit = load_protocol()
    events, rows, report = evaluate_oos(
        feature_frame, price_frames, folds, protocol
    )
    args.event_csv.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(args.event_csv, index=False, float_format="%.12g")
    pd.DataFrame(rows).to_csv(
        args.summary_csv, index=False, float_format="%.12g"
    )
    report.update({
        "snapshot_id": manifest["snapshot_id"],
        "snapshot_sha256": manifest["snapshot_sha256"],
        "features_sha256": _sha256(args.features),
        "folds_sha256": _sha256(args.folds),
        "protocol": protocol_audit,
    })
    args.report_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
