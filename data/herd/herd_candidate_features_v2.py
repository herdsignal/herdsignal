"""사전등록 V2 계산식으로 완료 주봉 HERD 후보 feature/label 패널을 생성한다."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

from herd.herd_candidate_protocol_v2 import load_and_validate
from herd.validation_universe import TICKER_SECTOR_ETF
from herd.weekly_rsi_events import completed_weekly_bars, wilder_rsi


def _slope(values: pd.Series) -> float:
    array = np.log(values.astype(float).to_numpy())
    return float(np.polyfit(np.arange(len(array)), array, 1)[0])


def _trend_quality(values: pd.Series) -> float:
    array = np.log(values.astype(float).to_numpy())
    x = np.arange(len(array))
    slope, intercept = np.polyfit(x, array, 1)
    if slope <= 0:
        return 0.0
    total = float(np.square(array - array.mean()).sum())
    return float(1 - np.square(array - (intercept + slope * x)).sum() / total) if total else 0.0


def _daily_features(stock: pd.DataFrame, sector: pd.DataFrame, spy: pd.DataFrame) -> pd.DataFrame:
    def close(frame):
        return frame.set_index("Date")["Adj Close"].sort_index().astype(float)
    stock_close, sector_close, spy_close = close(stock), close(sector), close(spy)
    aligned = pd.concat(
        {"stock": stock_close, "sector": sector_close, "spy": spy_close},
        axis=1,
        sort=False,
    ).sort_index().ffill()
    ratio = aligned["stock"] / aligned["sector"]
    high = aligned["stock"].rolling(252, min_periods=252).max()
    high_failure = []
    for index in range(len(aligned)):
        if index < 251:
            high_failure.append(np.nan)
            continue
        window = aligned["stock"].iloc[index - 251:index + 1].to_numpy()
        sessions_since = 251 - int(np.argmax(window))
        weeks_since = sessions_since / 5
        distance = high.iloc[index] / aligned["stock"].iloc[index] - 1
        high_failure.append(.5 * min(weeks_since / 26, 1) + .5 * min(distance / .20, 1))
    stock_indexed = stock.set_index("Date").sort_index()
    signed = np.sign(stock_close.pct_change(fill_method=None)) * stock_indexed["Volume"].astype(float)
    signed_volume = -(signed.rolling(20).sum() / stock_indexed["Volume"].astype(float).rolling(20).sum())
    spy_return = spy_close.pct_change(fill_method=None)
    spy_vol = spy_return.rolling(63).std(ddof=1) * np.sqrt(252)
    vol_pct = spy_vol.expanding(126).rank(pct=True)
    spy_dd = spy_close / spy_close.rolling(63).max() - 1
    stress = .4 * (spy_close < spy_close.rolling(200).mean()).astype(float) + .3 * vol_pct + .3 * (-spy_dd).clip(0, .30) / .30
    return pd.DataFrame({
        "STOCK_SECTOR_RS_13W": aligned["stock"].pct_change(63) - aligned["sector"].pct_change(63),
        "STOCK_SECTOR_RS_DAMAGE": ratio.rolling(63).max() / ratio - 1,
        "STOCK_SPY_RS_13W": aligned["stock"].pct_change(63) - aligned["spy"].pct_change(63),
        "HIGH_52W_PROXIMITY": aligned["stock"] / high,
        "HIGH_52W_FAILURE": high_failure,
        "SIGNED_VOLUME_PARTICIPATION": signed_volume,
        "MARKET_STRESS_REGIME": stress.reindex(aligned.index).ffill()
    }, index=aligned.index)


def _weekly_rows(ticker: str, stock: pd.DataFrame, daily: pd.DataFrame, rsi_entries: set[pd.Timestamp]) -> pd.DataFrame:
    weekly = completed_weekly_bars(stock)
    weekly["weekly_rsi"] = wilder_rsi(weekly["Adj Close"], 14)
    rows = []
    for index in range(26, len(weekly) - 26):
        date = weekly.index[index]
        last_session = pd.Timestamp(weekly["last_session"].iloc[index])
        current = weekly["Adj Close"].iloc[index - 25:index + 1]
        prior = weekly["Adj Close"].iloc[index - 25:index - 12]
        recent = weekly["Adj Close"].iloc[index - 12:index + 1]
        path13 = weekly["Adj Close"].iloc[index + 1:index + 14]
        path26 = weekly["Adj Close"].iloc[index + 1:index + 27]
        start = float(weekly["Adj Close"].iloc[index])
        point = daily.loc[:last_session].iloc[-1]
        rows.append({
            "ticker": ticker, "signal_date": date, "last_observed_session": last_session,
            **{column: float(point[column]) for column in daily.columns},
            "TREND_26W_QUALITY": _trend_quality(current),
            "TREND_13W_DECELERATION": 52 * (_slope(prior) - _slope(recent)),
            "WEEKLY_RSI_EXTREME": float(date in rsi_entries),
            "CONTINUATION_13W": bool(path13.iloc[-1] > start and path13.min() / start - 1 > -.10),
            "PULLBACK_13W": bool(path13.min() / start - 1 <= -.05),
            "STRUCTURAL_BREAK_26W": bool(path26.iloc[-1] / start - 1 <= -.10 and path26.min() / start - 1 <= -.15)
        })
    return pd.DataFrame(rows)


def _attach_business(panel: pd.DataFrame, business: pd.DataFrame) -> pd.DataFrame:
    parts = []
    business = business.copy()
    business["month_end"] = pd.to_datetime(business["month_end"])
    business["latest_fact_accepted_at"] = pd.to_datetime(business["latest_fact_accepted_at"], utc=True, errors="coerce").dt.tz_localize(None)
    for ticker, rows in panel.groupby("ticker"):
        facts = business[(business["ticker"] == ticker) & (business["entity_type"] == "GENERAL")].sort_values("month_end")
        left = rows.sort_values("signal_date")
        if facts.empty:
            left["PIT_BUSINESS_DETERIORATION"] = np.nan
        else:
            merged = pd.merge_asof(left, facts[["month_end", "flag_count", "latest_fact_accepted_at"]], left_on="signal_date", right_on="month_end", direction="backward")
            valid = merged["latest_fact_accepted_at"].isna() | (merged["latest_fact_accepted_at"] <= merged["signal_date"])
            merged["PIT_BUSINESS_DETERIORATION"] = (merged["flag_count"] / 4).where(valid)
            left = merged.drop(columns=["month_end", "flag_count", "latest_fact_accepted_at"])
        parts.append(left)
    return pd.concat(parts, ignore_index=True)


def build_panel(frames: dict[str, pd.DataFrame], events: pd.DataFrame, business: pd.DataFrame) -> pd.DataFrame:
    entries = events[events["event_type"] == "EXTREME_ENTRY"].copy()
    entries["event_date"] = pd.to_datetime(entries["event_date"])
    parts = []
    spy = frames["SPY"]
    for ticker, stock in frames.items():
        if ticker not in TICKER_SECTOR_ETF:
            continue
        daily = _daily_features(stock, frames[TICKER_SECTOR_ETF[ticker]], spy)
        dates = set(entries.loc[entries["ticker"] == ticker, "event_date"])
        parts.append(_weekly_rows(ticker, stock, daily, dates))
    return _attach_business(pd.concat(parts, ignore_index=True), business)


def _load_frames(snapshot: Path) -> dict[str, pd.DataFrame]:
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    frames = {}
    for ticker, item in manifest["files"].items():
        with gzip.open(snapshot / item["path"], "rt", encoding="utf-8") as stream:
            frames[ticker] = pd.read_csv(stream, parse_dates=["Date"])
    return frames


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--business", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    protocol, _ = load_and_validate()
    panel = build_panel(_load_frames(args.snapshot), pd.read_csv(args.events), pd.read_csv(args.business))
    feature_ids = [item["id"] for item in protocol["features"]]
    report = {
        "report_version":"herd-candidate-feature-panel-v2", "rows":len(panel),
        "tickers":int(panel["ticker"].nunique()), "features":len(feature_ids),
        "missing_fraction":{key:float(panel[key].isna().mean()) for key in feature_ids},
        "labels_are_not_features":True, "operational_action_ratio":0.0
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.output, index=False)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
