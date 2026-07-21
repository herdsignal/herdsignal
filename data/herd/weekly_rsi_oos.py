"""사전 고정한 matched-control 방식으로 주봉 RSI 사건을 독립 OOS 평가한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from scipy.stats import binomtest

from herd.weekly_rsi_events import completed_weekly_bars, load_snapshot_frames, wilder_rsi


PROTOCOL_PATH = Path(__file__).with_name("weekly_rsi_oos_protocol_v1.json")


def load_protocol(path: Path = PROTOCOL_PATH) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("protocol_version") != "HERD_WEEKLY_RSI_OOS_V1" \
            or protocol.get("status") != "LOCKED_BEFORE_OOS_RESULTS":
        raise ValueError("weekly RSI OOS protocol is not locked")
    return protocol


def _weekly_candidates(frames: dict[str, pd.DataFrame], horizons: int = 13) -> pd.DataFrame:
    rows = []
    for ticker, frame in frames.items():
        weekly = completed_weekly_bars(frame)
        weekly["weekly_rsi"] = wilder_rsi(weekly["Adj Close"], 14)
        weekly["trailing_26w_return"] = weekly["Adj Close"].pct_change(26, fill_method=None)
        for index in range(26, len(weekly) - horizons):
            future = weekly["Adj Close"].iloc[index + 1:index + horizons + 1]
            start = float(weekly["Adj Close"].iloc[index])
            rows.append({
                "ticker": ticker, "date": weekly.index[index],
                "weekly_rsi": float(weekly["weekly_rsi"].iloc[index]),
                "trailing_26w_return": float(weekly["trailing_26w_return"].iloc[index]),
                "target_hit": bool(float(future.min() / start - 1) <= -0.05),
            })
    return pd.DataFrame(rows)


def _assign_fold(frame: pd.DataFrame, folds: pd.DataFrame, date_column: str) -> pd.DataFrame:
    parts = []
    dates = pd.to_datetime(frame[date_column])
    for fold in folds.itertuples(index=False):
        selected = frame[dates.between(pd.Timestamp(fold.test_start), pd.Timestamp(fold.test_end))].copy()
        selected["fold_id"] = fold.fold_id
        parts.append(selected)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def _pool_mask(candidates: pd.DataFrame, control_pool: str) -> pd.Series:
    rsi = candidates["weekly_rsi"]
    if "RSI_70_TO_75" in control_pool:
        return rsi.between(70, 75, inclusive="left")
    if "RSI_55_TO_70" in control_pool:
        return rsi.between(55, 70, inclusive="left")
    return rsi >= 75


def _match_hypothesis(
    hypothesis: dict,
    events: pd.DataFrame,
    candidates: pd.DataFrame,
    protocol: dict,
) -> pd.DataFrame:
    treatments = events[events["event_type"] == hypothesis["event_type"]].copy()
    event_keys = set(zip(events["ticker"], pd.to_datetime(events["event_date"])))
    pool = candidates[_pool_mask(candidates, hypothesis["control_pool"])].copy()
    pool = pool[~pool.apply(lambda row: (row["ticker"], pd.Timestamp(row["date"])) in event_keys, axis=1)]
    rows = []
    caliper = protocol["matching"]["maximum_absolute_trailing_return_gap"]
    for (fold_id, ticker), treatment_group in treatments.groupby(["fold_id", "ticker"]):
        available = pool[(pool["fold_id"] == fold_id) & (pool["ticker"] == ticker)].copy()
        forbidden_dates = pd.to_datetime(treatment_group["event_date"])
        for date in forbidden_dates:
            available = available[~pd.to_datetime(available["date"]).between(date, date + pd.Timedelta(weeks=26))]
        used = set()
        for treatment in treatment_group.sort_values("event_date").itertuples(index=False):
            choices = available[~available.index.isin(used)].copy()
            if choices.empty:
                continue
            choices["gap"] = (choices["trailing_26w_return"] - treatment.trailing_26w_return).abs()
            control = choices.sort_values(["gap", "date"]).iloc[0]
            if control["gap"] > caliper:
                continue
            used.add(control.name)
            rows.append({
                "hypothesis_id": hypothesis["id"], "fold_id": fold_id, "ticker": ticker,
                "event_date": treatment.event_date, "control_date": control["date"],
                "event_target_hit": bool(treatment.target_hit),
                "control_target_hit": bool(control["target_hit"]),
                "pair_difference": int(treatment.target_hit) - int(control["target_hit"]),
                "trailing_return_gap": float(control["gap"]),
            })
    return pd.DataFrame(rows)


def evaluate(events: pd.DataFrame, frames: dict[str, pd.DataFrame], folds: pd.DataFrame, protocol: dict):
    candidates = _assign_fold(_weekly_candidates(frames), folds, "date")
    event_source = events.copy()
    event_source["event_date"] = pd.to_datetime(event_source["event_date"])
    event_source = event_source.merge(
        candidates[["ticker", "date", "trailing_26w_return", "target_hit"]],
        left_on=["ticker", "event_date"], right_on=["ticker", "date"], how="inner"
    )
    event_source = _assign_fold(event_source, folds, "event_date")
    pair_parts = [_match_hypothesis(h, event_source, candidates, protocol) for h in protocol["hypotheses"]]
    pairs = pd.concat([part for part in pair_parts if not part.empty], ignore_index=True)
    rows = []
    gate = protocol["adoption_gate"]
    for hypothesis in protocol["hypotheses"]:
        sample = pairs[pairs["hypothesis_id"] == hypothesis["id"]]
        fold_gaps = sample.groupby("fold_id")["pair_difference"].mean() if not sample.empty else pd.Series(dtype=float)
        date_gaps = sample.groupby("event_date")["pair_difference"].mean() if not sample.empty else pd.Series(dtype=float)
        positive_dates = int((date_gaps > 0).sum())
        negative_dates = int((date_gaps < 0).sum())
        informative_dates = positive_dates + negative_dates
        p_value = (
            float(binomtest(positive_dates, informative_dates, .5, alternative="greater").pvalue)
            if informative_dates else 1.0
        )
        event_rate = float(sample["event_target_hit"].mean()) if not sample.empty else None
        control_rate = float(sample["control_target_hit"].mean()) if not sample.empty else None
        rows.append({
            "hypothesis_id": hypothesis["id"], "matched_events": len(sample),
            "tickers": int(sample["ticker"].nunique()), "test_folds": int(sample["fold_id"].nunique()),
            "directional_folds": int((fold_gaps > 0).sum()), "signal_dates": len(date_gaps),
            "informative_signal_dates": informative_dates,
            "event_target_rate": event_rate, "control_target_rate": control_rate,
            "target_rate_gap": event_rate - control_rate if event_rate is not None else None,
            "raw_p_value": p_value
        })
    order = sorted(range(len(rows)), key=lambda i: rows[i]["raw_p_value"])
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, rows[index]["raw_p_value"] * (len(rows) - rank)))
        rows[index]["holm_p_value"] = running
    for row in rows:
        row["passed"] = bool(
            row["matched_events"] >= gate["minimum_matched_events"]
            and row["tickers"] >= gate["minimum_tickers"]
            and row["test_folds"] >= gate["minimum_test_folds"]
            and row["directional_folds"] >= gate["minimum_directional_folds"]
            and row["signal_dates"] >= gate["minimum_signal_dates"]
            and row["event_target_rate"] is not None and row["event_target_rate"] >= gate["minimum_event_target_rate"]
            and row["target_rate_gap"] >= gate["minimum_target_rate_gap"]
            and row["holm_p_value"] <= gate["maximum_holm_p_value"]
        )
    summary = pd.DataFrame(rows)
    passed = summary[summary["passed"]]["hypothesis_id"].tolist()
    report = {
        "report_version": "herd-weekly-rsi-oos-v1", "matched_pairs": len(pairs),
        "passing_hypotheses": passed, "profit_take_evidence_ready": bool(passed),
        "operational_action_ratio": 0.0, "blind_holdout_access": False
    }
    return pairs, summary, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--folds", type=Path, required=True)
    parser.add_argument("--pairs", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    pairs, summary, report = evaluate(
        pd.read_csv(args.events), load_snapshot_frames(args.snapshot), pd.read_csv(args.folds), load_protocol()
    )
    args.pairs.parent.mkdir(parents=True, exist_ok=True)
    pairs.to_csv(args.pairs, index=False)
    summary.to_csv(args.summary, index=False)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
