"""사전등록된 Rush 생애주기 전환이 이후 하락을 예고하는지 OOS 검증한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

from herd.data_snapshot import load_snapshot
from herd.rush_turning_point_protocol import load_protocol
from herd.timing_evidence_oos import build_scores

RUSH_STATES = (
    "HEALTHY_RUSH",
    "EXTENDING_RUSH",
    "EXHAUSTED_RUSH",
    "BREAKING_RUSH",
)
TREATMENT_STATES = {"EXHAUSTED_RUSH", "BREAKING_RUSH"}
CONTROL_STATES = {"HEALTHY_RUSH", "EXTENDING_RUSH"}
ETF_TICKERS = {"DIA", "IWM", "QQQ", "SPY"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_rush_states(
    closes: pd.DataFrame,
    volumes: pd.DataFrame,
    protocol: dict,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """과거와 현재 데이터만으로 월말 Rush 상태를 결정한다."""
    close = closes.sort_index().ffill(limit=3)
    volume = volumes.reindex_like(close).fillna(0)
    equity = [column for column in close if column not in ETF_TICKERS]
    monthly = close.resample("ME").last()
    stock = monthly[equity]
    spy = monthly["SPY"]

    fast_return = stock.pct_change(3, fill_method=None)
    slow_return = stock.pct_change(12, fill_method=None)
    fast_rate = fast_return / 3
    slow_rate = slow_return / 12
    fast_slow_gap = fast_rate - slow_rate
    relative_fast = fast_return.sub(
        spy.pct_change(3, fill_method=None), axis=0
    )
    relative_slow = slow_return.sub(
        spy.pct_change(12, fill_method=None), axis=0
    ) / 4
    relative_gap = relative_fast - relative_slow
    evidence_scores = build_scores(close, volume)
    participation = evidence_scores["PARTICIPATION"]
    participation_change = participation.diff(3)
    extension = evidence_scores["PRICE_EXTENSION"]
    ma50 = close.rolling(50, min_periods=50).mean().resample("ME").last()[equity]

    minimum_extension = protocol["rush_eligibility"][
        "price_extension_score_minimum"
    ]
    minimum_slow = protocol["rush_eligibility"][
        "slow_trend_12m_return_minimum"
    ]
    eligible = (extension >= minimum_extension) & (slow_return > minimum_slow)
    prior_rush = eligible.shift(1).rolling(3, min_periods=1).max().fillna(False)

    extending = (
        eligible
        & (fast_rate >= slow_rate)
        & (participation_change >= 0)
        & (relative_gap >= 0)
    )
    exhausted = (
        eligible
        & (fast_slow_gap < 0)
        & (fast_slow_gap.diff() < 0)
        & (participation_change < 0)
        & (relative_gap < 0)
    )
    breaking = (
        prior_rush.astype(bool)
        & (fast_return < 0)
        & (stock < ma50)
        & (relative_fast < 0)
    )

    states = pd.DataFrame("NONE", index=stock.index, columns=equity)
    states = states.mask(eligible, "HEALTHY_RUSH")
    states = states.mask(extending, "EXTENDING_RUSH")
    states = states.mask(exhausted, "EXHAUSTED_RUSH")
    states = states.mask(breaking, "BREAKING_RUSH")
    features = {
        "extension": extension,
        "fast_return": fast_return,
        "slow_return": slow_return,
        "fast_slow_gap": fast_slow_gap,
        "participation_change": participation_change,
        "relative_gap": relative_gap,
        "relative_fast": relative_fast,
        "ma50": ma50,
    }
    return states, features


def extract_transition_events(states: pd.DataFrame) -> pd.DataFrame:
    """같은 상태의 연속 월은 제외하고 상태 진입 첫 달만 사건으로 만든다."""
    rows = []
    previous = states.shift(1)
    for date in states.index:
        changed = states.loc[date].ne(previous.loc[date])
        current = states.loc[date]
        for ticker, state in current[changed & current.isin(RUSH_STATES)].items():
            rows.append({"signal_date": date, "ticker": ticker, "state": state})
    return pd.DataFrame(rows, columns=["signal_date", "ticker", "state"])


def _add_forward_outcomes(
    events: pd.DataFrame,
    closes: pd.DataFrame,
    horizon: int,
) -> pd.DataFrame:
    rows = []
    for event in events.itertuples(index=False):
        date = pd.Timestamp(event.signal_date)
        end = date + pd.offsets.MonthEnd(horizon)
        current_rows = closes.loc[closes.index <= date, event.ticker]
        future = closes.loc[
            (closes.index > date) & (closes.index <= end), event.ticker
        ].dropna()
        if current_rows.empty or future.empty:
            continue
        start_price = float(current_rows.iloc[-1])
        rows.append({
            "signal_date": date,
            "ticker": event.ticker,
            "state": event.state,
            "horizon_months": horizon,
            "outcome_end": end,
            "forward_return": float(future.iloc[-1] / start_price - 1),
            "forward_trough_return": float(future.min() / start_price - 1),
        })
    return pd.DataFrame(rows)


def select_non_overlapping_events(events: pd.DataFrame) -> pd.DataFrame:
    """종목·fold·기간 안에서 결과 구간이 겹치는 후속 사건을 제거한다."""
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
    count = len(ordered)
    for rank, (index, row) in enumerate(ordered):
        running = max(running, min(1.0, row["raw_p_value"] * (count - rank)))
        rows[index]["holm_p_value"] = running


def evaluate_oos(
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
    volumes = pd.concat({
        ticker: frame.assign(
            Date=pd.to_datetime(frame["Date"])
        ).set_index("Date")["Volume"]
        for ticker, frame in price_frames.items()
    }, axis=1).sort_index()
    states, _ = build_rush_states(closes, volumes, protocol)
    transitions = extract_transition_events(states)
    all_events = []
    horizons = protocol["observation"]["forward_horizons_months"]
    for horizon in horizons:
        outcomes = _add_forward_outcomes(transitions, closes, horizon)
        for fold in folds:
            start = pd.Timestamp(fold["test_start"])
            end = pd.Timestamp(fold["test_end"])
            eligible = outcomes.loc[
                outcomes["signal_date"].between(start, end)
                & (outcomes["outcome_end"] <= end)
            ].copy()
            eligible["fold_id"] = fold["fold_id"]
            all_events.append(eligible)
    events = (
        pd.concat(all_events, ignore_index=True)
        if all_events else pd.DataFrame()
    )
    events = select_non_overlapping_events(events)
    events["group"] = np.where(
        events["state"].isin(TREATMENT_STATES), "TREATMENT", "CONTROL"
    )

    rows = []
    for horizon in horizons:
        subset = events.loc[events["horizon_months"] == horizon]
        for outcome in ("forward_return", "forward_trough_return"):
            treatment = subset.loc[subset["group"] == "TREATMENT", outcome]
            control = subset.loc[subset["group"] == "CONTROL", outcome]
            fold_gaps = {}
            for fold_id, fold_rows in subset.groupby("fold_id"):
                left = fold_rows.loc[
                    fold_rows["group"] == "TREATMENT", outcome
                ]
                right = fold_rows.loc[
                    fold_rows["group"] == "CONTROL", outcome
                ]
                if not left.empty and not right.empty:
                    fold_gaps[fold_id] = float(
                        right.median() - left.median()
                    )
            p_value = (
                float(mannwhitneyu(
                    treatment, control, alternative="less"
                ).pvalue)
                if not treatment.empty and not control.empty else 1.0
            )
            rows.append({
                "horizon_months": horizon,
                "outcome": outcome,
                "treatment_events": int(len(treatment)),
                "control_events": int(len(control)),
                "treatment_folds": int(
                    subset.loc[subset["group"] == "TREATMENT", "fold_id"].nunique()
                ),
                "control_folds": int(
                    subset.loc[subset["group"] == "CONTROL", "fold_id"].nunique()
                ),
                "directional_folds": int(sum(gap > 0 for gap in fold_gaps.values())),
                "median_treatment": (
                    float(treatment.median()) if not treatment.empty else None
                ),
                "median_control": (
                    float(control.median()) if not control.empty else None
                ),
                "control_minus_treatment": (
                    float(control.median() - treatment.median())
                    if not treatment.empty and not control.empty else None
                ),
                "raw_p_value": p_value,
                "fold_gap_json": json.dumps(
                    fold_gaps, sort_keys=True, separators=(",", ":")
                ),
            })
    _holm_adjust(rows)

    gate = protocol["adoption_gate"]
    for row in rows:
        minimum_gap = (
            gate["minimum_return_gap"]
            if row["outcome"] == "forward_return"
            else gate["minimum_trough_gap"]
        )
        row["outcome_pass"] = (
            row["treatment_events"] >= gate["minimum_events_per_side"]
            and row["control_events"] >= gate["minimum_events_per_side"]
            and row["treatment_folds"] >= gate["minimum_test_folds_per_side"]
            and row["control_folds"] >= gate["minimum_test_folds_per_side"]
            and row["directional_folds"] >= gate["minimum_directional_folds"]
            and row["holm_p_value"] <= gate["maximum_holm_p_value"]
            and row["control_minus_treatment"] is not None
            and row["control_minus_treatment"] > minimum_gap
        )
    primary = [
        row for row in rows
        if row["horizon_months"] == gate["primary_horizon_months"]
    ]
    passed = sum(row["outcome_pass"] for row in primary)
    decision = (
        "PASS_TO_PARTIAL_PROFIT_TAKE_ABLATION"
        if passed >= gate["required_primary_outcomes"]
        else "REJECT_RUSH_TURNING_POINT_SELL_EVIDENCE"
    )
    report = {
        "report_version": "herd-rush-turning-point-oos-v1",
        "decision": decision,
        "primary_outcomes_passed": passed,
        "primary_outcomes_required": gate["required_primary_outcomes"],
        "state_event_counts": {
            state: int((events["state"] == state).sum()) for state in RUSH_STATES
        },
        "limitations": [
            "The fixed price universe remains survivorship-biased.",
            "Relative strength uses SPY because PIT sector ETF mapping is unavailable.",
            "Volume participation is a proxy and does not represent full market breadth.",
            "This event study does not authorize re-entry or live trading."
        ],
    }
    return events, rows, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("folds", type=Path)
    parser.add_argument("event_csv", type=Path)
    parser.add_argument("summary_csv", type=Path)
    parser.add_argument("report_json", type=Path)
    args = parser.parse_args()
    frames, manifest = load_snapshot(args.snapshot)
    folds = pd.read_csv(args.folds, dtype=str).to_dict("records")
    protocol, protocol_audit = load_protocol()
    events, rows, report = evaluate_oos(frames, folds, protocol)
    args.event_csv.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(args.event_csv, index=False, float_format="%.12g")
    pd.DataFrame(rows).to_csv(
        args.summary_csv, index=False, float_format="%.12g"
    )
    report.update({
        "snapshot_id": manifest["snapshot_id"],
        "snapshot_sha256": manifest["snapshot_sha256"],
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
