"""사전등록된 매수·익절 방향 사건을 고정 fold에서 독립 검증한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

from herd.action_direction_hypotheses import load_registry
from herd.data_snapshot import load_snapshot


ETF_TICKERS = {"DIA", "IWM", "QQQ", "SPY"}
EXPECTED_SIGN = {"NEW_ENTRY": 1, "ADD_BUY": 1, "PROFIT_TAKE": -1}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _daily_matrix(frames: dict[str, pd.DataFrame], column: str) -> pd.DataFrame:
    return pd.concat({
        ticker: frame.assign(Date=pd.to_datetime(frame["Date"]))
        .set_index("Date")[column]
        for ticker, frame in frames.items()
    }, axis=1).sort_index()


def build_event_flags(
    frames: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """현재 월말까지의 가격만 사용해 사전등록 사건을 계산한다."""
    close = _daily_matrix(frames, "Close").ffill(limit=3)
    high = _daily_matrix(frames, "High").reindex_like(close)
    low = _daily_matrix(frames, "Low").reindex_like(close)
    monthly_close = close.resample("ME").last()
    equities = [ticker for ticker in close if ticker not in ETF_TICKERS]

    ret21_daily = close.pct_change(21, fill_method=None)
    ret63_daily = close.pct_change(63, fill_method=None)
    ret252_daily = close.pct_change(252, fill_method=None)
    drawdown21_daily = close.div(
        close.rolling(21, min_periods=21).max()
    ).sub(1)
    ret21 = ret21_daily.resample("ME").last()[equities]
    ret63 = ret63_daily.resample("ME").last()[equities]
    ret252 = ret252_daily.resample("ME").last()[equities]
    drawdown21 = drawdown21_daily.resample("ME").last()[equities]

    entry = (
        ret252.gt(0)
        & drawdown21.ge(-0.20)
        & drawdown21.le(-0.05)
        & ret21.gt(0)
        & ret21.shift(1).le(0)
    )

    spy21 = ret21_daily["SPY"].resample("ME").last()
    residual21 = ret21.sub(spy21, axis=0)
    add_buy = (
        drawdown21.ge(-0.25)
        & drawdown21.le(-0.08)
        & pd.DataFrame(
            np.repeat(
                spy21.lt(0).reindex(drawdown21.index).to_numpy()[:, None],
                len(equities), axis=1,
            ),
            index=drawdown21.index,
            columns=equities,
        )
        & residual21.gt(-0.10)
    )

    previous_close = close.shift(1)
    true_range = pd.concat(
        [high.sub(low), high.sub(previous_close).abs(), low.sub(previous_close).abs()],
        keys=["hl", "hc", "lc"],
    ).groupby(level=1).max()
    atr63 = true_range.rolling(63, min_periods=40).mean()
    extension = close.sub(close.rolling(200, min_periods=200).mean()).div(atr63)
    profit_extension = extension.resample("ME").last()[equities].ge(3)

    deceleration = ret63.sub(ret252.div(4))
    profit_deceleration = deceleration.lt(0) & deceleration.shift(1).ge(0)

    flags = {
        "ENTRY_TREND_RESUMPTION": entry,
        "ADD_BUY_MARKET_SECTOR_DISLOCATION": add_buy,
        "PROFIT_TAKE_VOLATILITY_EXTENSION": profit_extension,
        "PROFIT_TAKE_TREND_DECELERATION": profit_deceleration,
    }
    availability = {
        key: "READY" for key in flags
    }
    availability["PROFIT_TAKE_RELATIVE_STRENGTH_BREAK"] = (
        "DATA_BLOCKED_SECTOR_ETF_NOT_IN_FROZEN_SNAPSHOT"
    )
    availability["REENTRY_POST_PROFIT_STABILIZATION"] = (
        "DEPENDENCY_BLOCKED_PROFIT_AND_BUSINESS_EVIDENCE_REQUIRED"
    )
    return flags, availability


def _forward_outcome(
    close: pd.DataFrame, month_ends: pd.DatetimeIndex, horizon: int, trough: bool,
) -> pd.DataFrame:
    if not trough:
        monthly = close.resample("ME").last()
        return monthly.shift(-horizon).div(monthly).sub(1)
    rows: dict[pd.Timestamp, pd.Series] = {}
    for signal_date in month_ends:
        start_rows = close.loc[close.index <= signal_date]
        future = close.loc[
            (close.index > signal_date)
            & (close.index <= signal_date + pd.offsets.MonthEnd(horizon))
        ]
        if not start_rows.empty and not future.empty:
            rows[signal_date] = future.min().div(start_rows.iloc[-1]).sub(1)
    return pd.DataFrame.from_dict(rows, orient="index").reindex(columns=close.columns)


def _holm(rows: list[dict]) -> None:
    ordered = sorted(enumerate(rows), key=lambda item: item[1]["raw_p_value"])
    running = 0.0
    for rank, (index, row) in enumerate(ordered):
        running = max(running, min(1.0, (len(ordered) - rank) * row["raw_p_value"]))
        rows[index]["holm_p_value"] = running


def evaluate_oos(
    frames: dict[str, pd.DataFrame], folds: list[dict], registry: dict,
) -> tuple[list[dict], dict]:
    flags, availability = build_event_flags(frames)
    close = _daily_matrix(frames, "Close").ffill(limit=3)
    equities = [ticker for ticker in close if ticker not in ETF_TICKERS]
    month_ends = close.resample("ME").last().index
    gate = registry["common_contract"]
    hypotheses = {row["id"]: row for row in registry["hypotheses"]}
    rows: list[dict] = []

    for hypothesis_id, event in flags.items():
        hypothesis = hypotheses[hypothesis_id]
        sign = EXPECTED_SIGN[hypothesis["action"]]
        for horizon in hypothesis["horizons_months"]:
            for outcome_name, trough in (("FORWARD_RETURN", False), ("FORWARD_TROUGH", True)):
                outcome = _forward_outcome(close[equities], month_ends, horizon, trough)
                fold_ics: dict[str, float] = {}
                inference_ics: list[float] = []
                observations = events = 0
                for fold in folds:
                    start, end = pd.Timestamp(fold["test_start"]), pd.Timestamp(fold["test_end"])
                    eligible = event.index[
                        (event.index >= start)
                        & (event.index <= end)
                        & (event.index + pd.offsets.MonthEnd(horizon) <= end)
                    ]
                    monthly_ics = []
                    for position, month in enumerate(eligible):
                        if month not in outcome.index:
                            continue
                        aligned = pd.concat(
                            [event.loc[month].rename("event").astype(float),
                             outcome.loc[month].rename("outcome")], axis=1,
                        ).dropna()
                        if len(aligned) < 20 or aligned["event"].nunique() < 2:
                            continue
                        ic = aligned["event"].corr(aligned["outcome"], method="spearman")
                        if pd.isna(ic):
                            continue
                        monthly_ics.append(float(ic))
                        observations += len(aligned)
                        events += int(aligned["event"].sum())
                        if position % horizon == 0:
                            inference_ics.append(float(ic) * sign)
                    if monthly_ics:
                        fold_ics[fold["fold_id"]] = float(np.median(monthly_ics))
                signed_folds = [value * sign for value in fold_ics.values()]
                positive = sum(value > 0 for value in inference_ics)
                raw_p = float(binomtest(
                    positive, len(inference_ics), 0.5, alternative="greater"
                ).pvalue) if inference_ics else 1.0
                rows.append({
                    "hypothesis_id": hypothesis_id,
                    "action": hypothesis["action"],
                    "horizon_months": horizon,
                    "outcome": outcome_name,
                    "folds": len(fold_ics),
                    "directional_folds": sum(value > 0 for value in signed_folds),
                    "signed_median_fold_ic": float(np.median(signed_folds)) if signed_folds else None,
                    "non_overlapping_ic_samples": len(inference_ics),
                    "stock_month_observations": observations,
                    "event_observations": events,
                    "raw_p_value": raw_p,
                    "fold_ic_json": json.dumps(fold_ics, sort_keys=True, separators=(",", ":")),
                })

    for action in EXPECTED_SIGN:
        _holm([row for row in rows if row["action"] == action])
    for row in rows:
        row["outcome_pass"] = (
            row["folds"] >= gate["minimum_directional_folds"]
            and row["directional_folds"] >= gate["minimum_directional_folds"]
            and row["signed_median_fold_ic"] is not None
            and row["signed_median_fold_ic"] >= gate["minimum_absolute_rank_ic"]
            and row["holm_p_value"] <= gate["maximum_adjusted_p_value"]
        )

    decisions = {}
    for hypothesis in registry["hypotheses"]:
        hypothesis_id = hypothesis["id"]
        if availability[hypothesis_id] != "READY":
            decisions[hypothesis_id] = availability[hypothesis_id]
            continue
        result_rows = [row for row in rows if row["hypothesis_id"] == hypothesis_id]
        passing_returns = sum(
            row["outcome_pass"] for row in result_rows if row["outcome"] == "FORWARD_RETURN"
        )
        decisions[hypothesis_id] = (
            "PASS_TO_ROLE_CORRECT_ABLATION"
            if passing_returns >= gate["minimum_passing_horizons"]
            else "REJECTED_DIRECTIONAL_EVIDENCE"
        )
    return rows, {
        "report_version": "herd-action-direction-oos-v1",
        "registry_version": registry["registry_version"],
        "decisions": decisions,
        "operational_authorization": False,
        "blind_holdout_access": False,
        "limitations": [
            "The frozen 55-ticker price universe remains survivorship-biased.",
            "Sector-relative evidence is blocked because sector ETFs are absent from the frozen snapshot.",
            "A pass authorizes only a role-correct ablation, never an operational action.",
            "Re-entry remains blocked until profit-taking and the SEC PIT business guard independently pass."
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("folds", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("output_json", type=Path)
    args = parser.parse_args()
    frames, manifest = load_snapshot(args.snapshot)
    folds = pd.read_csv(args.folds, dtype=str).to_dict("records")
    registry, registry_audit = load_registry()
    rows, report = evaluate_oos(frames, folds, registry)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.output_csv, index=False, float_format="%.12g", lineterminator="\n")
    report.update({
        "snapshot_id": manifest["snapshot_id"],
        "snapshot_sha256": manifest["snapshot_sha256"],
        "folds_sha256": _sha256(args.folds),
        "registry_audit": registry_audit,
    })
    args.output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
