"""고정 fold에서 HERD 가격 증거군의 역할별 OOS 예측력을 검증한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

from herd.data_snapshot import load_snapshot
from herd.timing_oos_protocol import load_protocol

FAMILIES = (
    "PRICE_EXTENSION",
    "TREND_MATURITY",
    "RELATIVE_OVERHEAT",
    "PARTICIPATION",
    "MARKET_RISK",
)
EXPECTED_SIGN = {
    "PRICE_EXTENSION": -1,
    "TREND_MATURITY": 1,
    "RELATIVE_OVERHEAT": -1,
    "PARTICIPATION": 1,
    "MARKET_RISK": -1,
}
ETF_TICKERS = {"DIA", "IWM", "QQQ", "SPY"}


class TimingEvidenceOosError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cross_rank(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.rank(axis=1, pct=True, method="average") * 100


def _monthly_rsi(close: pd.DataFrame, periods: int = 14) -> pd.DataFrame:
    monthly = close.resample("ME").last()
    delta = monthly.diff()
    gain = delta.clip(lower=0).ewm(
        alpha=1 / periods, adjust=False, min_periods=periods
    ).mean()
    loss = (-delta.clip(upper=0)).ewm(
        alpha=1 / periods, adjust=False, min_periods=periods
    ).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def build_scores(
    closes: pd.DataFrame,
    volumes: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """고정 수식이며 모든 rolling 계산은 현재 시점 이전 값만 사용한다."""
    close = closes.sort_index().ffill(limit=3)
    volume = volumes.reindex_like(close).fillna(0)
    monthly = close.resample("ME").last()
    equity = [column for column in close if column not in ETF_TICKERS]
    returns = close.pct_change(fill_method=None)
    vol63 = returns.rolling(63, min_periods=40).std().replace(0, np.nan)

    distance50 = (close / close.rolling(50, min_periods=50).mean() - 1) / vol63
    distance200 = (
        close / close.rolling(200, min_periods=200).mean() - 1
    ) / vol63
    rolling_low = close.rolling(252, min_periods=126).min()
    rolling_high = close.rolling(252, min_periods=126).max()
    range_position = (close - rolling_low) / (rolling_high - rolling_low)
    extension = sum((
        _cross_rank(distance50.resample("ME").last()[equity]),
        _cross_rank(distance200.resample("ME").last()[equity]),
        _cross_rank(_monthly_rsi(close)[equity]),
        _cross_rank(range_position.resample("ME").last()[equity]),
    )) / 4

    ret6 = monthly.pct_change(6, fill_method=None)[equity]
    ret12_1 = monthly.shift(1).pct_change(11, fill_method=None)[equity]
    ma50 = close.rolling(50, min_periods=50).mean()
    ma200 = close.rolling(200, min_periods=200).mean()
    slope50 = ma50.pct_change(63, fill_method=None).resample("ME").last()[equity]
    slope200 = ma200.pct_change(63, fill_method=None).resample("ME").last()[equity]
    recent3 = monthly.pct_change(3, fill_method=None)[equity]
    slow3 = monthly.pct_change(12, fill_method=None)[equity] / 4
    acceleration = recent3 - slow3
    trend = sum((
        _cross_rank(ret6),
        _cross_rank(ret12_1),
        _cross_rank(slope50),
        _cross_rank(slope200),
        _cross_rank(acceleration),
    )) / 5

    spy6 = monthly["SPY"].pct_change(6, fill_method=None)
    relative6 = ret6.sub(spy6, axis=0)
    relative_recent = monthly[equity].pct_change(
        3, fill_method=None
    ).sub(monthly["SPY"].pct_change(3, fill_method=None), axis=0)
    relative_slow = relative6 / 2
    relative_deceleration = relative_recent - relative_slow
    relative_overheat = (
        _cross_rank(relative6) + _cross_rank(-relative_deceleration)
    ) / 2

    signed_volume = volume.where(returns > 0, -volume.where(returns < 0, 0))
    participation_volume = signed_volume.rolling(
        63, min_periods=40
    ).sum() / volume.rolling(63, min_periods=40).sum().replace(0, np.nan)
    volume_ratio = volume.rolling(20, min_periods=20).mean() / volume.rolling(
        120, min_periods=80
    ).mean().replace(0, np.nan)
    breadth = (
        close[equity] > close[equity].rolling(200, min_periods=200).mean()
    ).mean(axis=1).resample("ME").last()
    breadth_frame = pd.DataFrame(
        np.repeat(breadth.to_numpy()[:, None], len(equity), axis=1),
        index=breadth.index,
        columns=equity,
    )
    participation = (
        _cross_rank(participation_volume.resample("ME").last()[equity])
        + _cross_rank(volume_ratio.resample("ME").last()[equity])
        + breadth_frame * 100
    ) / 3

    downside_vol = returns.where(returns < 0, 0).rolling(
        63, min_periods=40
    ).std().resample("ME").last()[equity]
    drawdown = (
        close / close.rolling(252, min_periods=126).max() - 1
    ).resample("ME").last()[equity]
    market_risk = (_cross_rank(downside_vol) + _cross_rank(-drawdown)) / 2
    return {
        "PRICE_EXTENSION": extension,
        "TREND_MATURITY": trend,
        "RELATIVE_OVERHEAT": relative_overheat,
        "PARTICIPATION": participation,
        "MARKET_RISK": market_risk,
    }


def _forward_trough_return(
    daily: pd.DataFrame,
    month_ends: pd.DatetimeIndex,
    horizon: int,
) -> pd.DataFrame:
    """월말 이후 horizon 동안 일별 종가의 최저 수익률을 계산한다."""
    rows = {}
    for signal_date in month_ends:
        end = signal_date + pd.offsets.MonthEnd(horizon)
        future = daily.loc[(daily.index > signal_date) & (daily.index <= end)]
        if future.empty:
            continue
        current_rows = daily.loc[daily.index <= signal_date]
        if current_rows.empty:
            continue
        current = current_rows.iloc[-1]
        rows[signal_date] = future.min().div(current).sub(1)
    return pd.DataFrame.from_dict(rows, orient="index").reindex(columns=daily.columns)


def _holm_adjust(rows: list[dict]) -> None:
    valid = [(index, row["raw_p_value"]) for index, row in enumerate(rows)]
    ordered = sorted(valid, key=lambda item: item[1])
    count = len(ordered)
    running = 0.0
    for rank, (index, p_value) in enumerate(ordered):
        adjusted = min(1.0, (count - rank) * p_value)
        running = max(running, adjusted)
        rows[index]["holm_p_value"] = running


def evaluate_oos(
    price_frames: dict[str, pd.DataFrame],
    folds: list[dict],
    protocol: dict,
) -> tuple[list[dict], dict]:
    closes = pd.concat({
        ticker: frame.assign(Date=pd.to_datetime(frame["Date"])).set_index("Date")["Close"]
        for ticker, frame in price_frames.items()
    }, axis=1).sort_index()
    volumes = pd.concat({
        ticker: frame.assign(Date=pd.to_datetime(frame["Date"])).set_index("Date")["Volume"]
        for ticker, frame in price_frames.items()
    }, axis=1).sort_index()
    scores = build_scores(closes, volumes)
    monthly = closes.resample("ME").last()
    equity = [column for column in monthly if column not in ETF_TICKERS]
    gate = protocol["predictive_gate"]
    detail = []
    summaries = []
    for family in FAMILIES:
        score = scores[family]
        for horizon in gate["forward_horizons_months"]:
            outcome = (
                _forward_trough_return(
                    closes[equity], monthly.index, horizon
                )
                if family == "MARKET_RISK"
                else monthly[equity].shift(-horizon).div(monthly[equity]).sub(1)
            )
            fold_ics = {}
            inference_ics = []
            observations = 0
            monthly_ic_count = 0
            for fold in folds:
                start = pd.Timestamp(fold["test_start"])
                end = pd.Timestamp(fold["test_end"])
                months = score.index[(score.index >= start) & (score.index <= end)]
                eligible = [
                    month for month in months
                    if month in outcome.index
                    and month + pd.offsets.MonthEnd(horizon) <= end
                ]
                monthly_ics = []
                for position, month in enumerate(eligible):
                    aligned = pd.concat(
                        [score.loc[month].rename("score"),
                         outcome.loc[month].rename("outcome")],
                        axis=1,
                    ).dropna()
                    if len(aligned) < 20:
                        continue
                    ic = aligned["score"].corr(
                        aligned["outcome"], method="spearman"
                    )
                    if pd.isna(ic):
                        continue
                    monthly_ics.append(float(ic))
                    monthly_ic_count += 1
                    observations += len(aligned)
                    if position % horizon == 0:
                        inference_ics.append(float(ic) * EXPECTED_SIGN[family])
                if monthly_ics:
                    fold_ics[fold["fold_id"]] = float(np.median(monthly_ics))
            signed_fold_ics = [
                value * EXPECTED_SIGN[family] for value in fold_ics.values()
            ]
            positive = sum(value > 0 for value in inference_ics)
            raw_p = (
                float(binomtest(
                    positive, len(inference_ics), 0.5, alternative="greater"
                ).pvalue)
                if inference_ics else 1.0
            )
            summaries.append({
                "family": family,
                "horizon_months": horizon,
                "expected_sign": EXPECTED_SIGN[family],
                "folds": len(fold_ics),
                "directional_folds": sum(value > 0 for value in signed_fold_ics),
                "monthly_ic_samples": monthly_ic_count,
                "non_overlapping_ic_samples": len(inference_ics),
                "stock_month_observations": observations,
                "signed_median_fold_ic": (
                    float(np.median(signed_fold_ics)) if signed_fold_ics else None
                ),
                "raw_p_value": raw_p,
                "fold_ic_json": json.dumps(
                    fold_ics, sort_keys=True, separators=(",", ":")
                ),
            })
            for fold_id, ic in fold_ics.items():
                detail.append({
                    "family": family,
                    "horizon_months": horizon,
                    "fold_id": fold_id,
                    "rank_ic": ic,
                    "signed_rank_ic": ic * EXPECTED_SIGN[family],
                })
    for family in FAMILIES:
        _holm_adjust([
            row for row in summaries if row["family"] == family
        ])
    family_decisions = {}
    for family in FAMILIES:
        family_rows = [row for row in summaries if row["family"] == family]
        for row in family_rows:
            row["horizon_pass"] = (
                row["signed_median_fold_ic"]
                is not None
                and row["signed_median_fold_ic"]
                >= gate["minimum_signed_median_rank_ic"]
                and row["directional_folds"] >= gate["minimum_directional_folds"]
                and row["holm_p_value"] <= gate["maximum_adjusted_p_value"]
            )
        passing = sum(row["horizon_pass"] for row in family_rows)
        family_decisions[family] = {
            "passing_horizons": passing,
            "required_horizons": gate["minimum_passing_horizons"],
            "decision": (
                (
                    "PASS_STOCK_DOWNSIDE_COMPONENT_TO_CAP_ABLATION"
                    if family == "MARKET_RISK"
                    else "PASS_TO_ROLE_CORRECT_ABLATION"
                )
                if passing >= gate["minimum_passing_horizons"]
                else "REJECTED_PREDICTIVE_EVIDENCE"
            ),
        }
    return summaries, {
        "report_version": "herd-timing-evidence-oos-v2",
        "families": family_decisions,
        "gate": gate,
        "limitations": [
            "Current fixed 55-ticker universe remains survivorship-biased.",
            "Sector ETF PIT prices are absent; relative evidence uses SPY only.",
            "MARKET_RISK pass covers stock downside-volatility and drawdown components; the common SPY regime needs a separate time-series test.",
            "Business guard is evaluated in a separate SEC PIT stage."
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
    fold_rows = pd.read_csv(args.folds, dtype=str).to_dict("records")
    protocol, protocol_audit = load_protocol()
    rows, report = evaluate_oos(frames, fold_rows, protocol)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(
        args.output_csv, index=False, float_format="%.12g", lineterminator="\n"
    )
    report.update({
        "snapshot_id": manifest["snapshot_id"],
        "snapshot_sha256": manifest["snapshot_sha256"],
        "protocol": protocol_audit,
        "folds_sha256": _sha256(args.folds),
    })
    args.output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
